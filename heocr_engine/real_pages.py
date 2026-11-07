"""Real printed pages pseudo-labelled by Tesseract, for segmentation training (R4f1; docs/training_run_contract.md).

`pseudo_label_pages` reads a folder of public-domain page scans and their provenance
(`heocr_real_scan_provenance.v1`, written by the operator's collection step outside this repository). It runs a local
Tesseract (psm 3, hOCR) on each page and writes a `heocr_real_pages.v1` manifest:
- **Lines:** Tesseract's lines (`ocr_line`, `ocr_header`, `ocr_caption`, `ocr_textfloat`).
  - The polygon is the line's own bounding box, unpadded: tight, since the recogniser is crop-sensitive.
  - The baseline is the hOCR `baseline`, clamped to the box.
  - A line with no words, or that is a speck, is dropped.
- **Regions:** each Tesseract block (`ocr_carea`) that keeps a line becomes a `body` region, the box around its kept
  lines.
- **Filter:** a page is kept only when its lines agree with a hand-free image proxy:
  - text rows counted in 12 narrow vertical strips, after Otsu binarisation and clearing long rules and frames;
  - Tesseract's rows per strip must fall in a set ratio of the proxy's;
  - plus a minimum line count. Word confidence is recorded, not filtered on.
  Rejected pages are listed with their reason.

Both fail closed unless every page's book is keyed (`index_key`, or `work_key` for other sources), outside the listed
evaluation Indexes, and admitted by hocrgen's public-domain gate (`gate.admitted: true`).

`load_real_pages` checks a manifest and its images, for `prepare_kraken_data(..., real_pages=...)`. Nothing here
calls a network; the Tesseract traineddata is user-supplied and hashed.
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import statistics

from heocr_engine.cli import EngineError, digest, inspect_image, read_limited, run_process

REAL_PAGES_SCHEMA = "heocr_real_pages.v1"
SCAN_PROVENANCE_SCHEMA = "heocr_real_scan_provenance.v1"
HEX64 = re.compile(r"[0-9a-f]{64}")
LINE_CLASSES = ("ocr_line", "ocr_header", "ocr_caption", "ocr_textfloat")
MAX_IMAGE_BYTES = 60_000_000
MAX_MANIFEST_BYTES = 200_000_000
STRIPS = 12
# Word confidence is recorded but not filtered on: on 19th-century prints Tesseract's recognition confidence is low
# (25-40) even where its layout analysis finds the lines well, and the proxy ratio is what rejects bad geometry.
FILTER = {"min_lines": 3, "min_line_height": 4, "min_line_width": 6, "proxy_ratio": [0.8, 1.25]}
REGION_TYPE = "body"


class _HocrParser(HTMLParser):
    """Blocks (ocr_carea) of lines, each line with its bbox, baseline and word confidences."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[list[dict]] = []
        self._stack: list[str | None] = []

    @staticmethod
    def _title(attrs) -> dict:
        title = dict(attrs).get("title") or ""
        fields = {}
        for part in title.split(";"):
            part = part.strip()
            if " " in part:
                key, value = part.split(" ", 1)
                fields[key] = value
        return fields

    def handle_starttag(self, tag, attrs):
        cls = dict(attrs).get("class")
        self._stack.append(cls)
        if cls == "ocr_carea":
            self.blocks.append([])
        elif cls in LINE_CLASSES:
            fields = self._title(attrs)
            if "bbox" in fields:
                if not self.blocks:
                    self.blocks.append([])
                slope, offset = (float(v) for v in fields.get("baseline", "0 0").split()[:2])
                self.blocks[-1].append({"class": cls, "bbox": [int(v) for v in fields["bbox"].split()[:4]],
                                        "slope": slope, "offset": offset, "confidences": []})
        elif cls == "ocrx_word" and self.blocks and self.blocks[-1]:
            fields = self._title(attrs)
            if "x_wconf" in fields:
                self.blocks[-1][-1]["confidences"].append(float(fields["x_wconf"]))

    def handle_endtag(self, tag):
        if self._stack:
            self._stack.pop()


def hocr_lines(hocr: str, width: int, height: int, rules: dict = FILTER) -> tuple[list[dict], list[dict], dict]:
    """Lines and `body` regions from Tesseract hOCR, plus counts of what was dropped and the mean confidence.

    Line polygons are the unpadded line boxes, clipped to the page; baselines follow hOCR's `baseline slope offset`
    (from the box's bottom-left corner), clamped into the box. Line indices are in Tesseract's reading order.
    """
    parser = _HocrParser()
    parser.feed(hocr)
    lines, regions = [], []
    dropped, confidences = 0, []
    for block in parser.blocks:
        members = []
        for raw in block:
            x0, y0, x1, y1 = raw["bbox"]
            x0, y0, x1, y1 = max(0, x0), max(0, y0), min(width, x1), min(height, y1)
            words = raw["confidences"]
            confidences.extend(words)
            if x1 - x0 < rules["min_line_width"] or y1 - y0 < rules["min_line_height"] or not words:
                dropped += 1
                continue
            base = lambda x: min(max(round(y1 + raw["offset"] + raw["slope"] * (x - x0)), y0), y1)  # noqa: E731
            members.append(len(lines))
            lines.append({"line_index": len(lines), "region": REGION_TYPE, "region_index": len(regions),
                          "polygon": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)],
                          "baseline": [(x0, base(x0)), (x1, base(x1))], "text": "",
                          "logical_line_index": None, "occluded": False, "tesseract_class": raw["class"]})
        if members:
            xs = [x for i in members for x, _ in lines[i]["polygon"]]
            ys = [y for i in members for _, y in lines[i]["polygon"]]
            box = (max(0, min(xs) - 2), max(0, min(ys) - 2), min(width, max(xs) + 2), min(height, max(ys) + 2))
            regions.append({"region_index": len(regions), "type": REGION_TYPE,
                            "polygon": [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])],
                            "line_indices": members})
    stats = {"lines_dropped": dropped,
             "mean_word_confidence": round(statistics.fmean(confidences), 2) if confidences else 0.0}
    return lines, regions, stats


def _otsu(histogram: list[int]) -> int:
    total = sum(histogram)
    sum_all = sum(i * h for i, h in enumerate(histogram))
    best, threshold, weight, partial = -1.0, 128, 0, 0
    for t in range(256):
        weight += histogram[t]
        if weight in (0, total):
            continue
        partial += t * histogram[t]
        mean_b, mean_f = partial / weight, (sum_all - partial) / (total - weight)
        between = weight * (total - weight) * (mean_b - mean_f) ** 2
        if between > best:
            best, threshold = between, t
    return threshold


def _runs(values) -> list[tuple[int, int]]:
    out, start = [], None
    for i, value in enumerate(values):
        if value and start is None:
            start = i
        elif not value and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(values)))
    return out


def strip_proxy(raw: bytes) -> list[tuple[int, int]]:
    """(x, text rows) for each of STRIPS narrow vertical strips: a column-agnostic, hand-free line-count proxy.

    Otsu-binarise; trim a 2% border; clear straight ink runs longer than 12% of the page along a row or a column
    (frames, rules); then count runs of inked rows in each strip (3% of the width), merging gaps of 1-2 px and
    dropping runs under 0.4x the strip's median run (diacritic rows, specks).
    """
    import io

    from PIL import Image
    try:
        import numpy as np
    except ImportError as exc:
        raise EngineError("The strip proxy needs numpy (pip install numpy, or the kraken extra)") from exc

    with Image.open(io.BytesIO(raw)) as image:
        gray = np.asarray(image.convert("L"))
    histogram = np.bincount(gray.ravel(), minlength=256).tolist()
    ink = gray <= _otsu(histogram)  # Otsu: the threshold value belongs to the dark class
    height, width = ink.shape
    by, bx = int(height * 0.02), int(width * 0.02)
    ink = ink[by:height - by, bx:width - bx].copy()
    for axis_view, limit in ((ink, 0.12 * ink.shape[1]), (ink.T, 0.12 * ink.shape[0])):
        for i in range(axis_view.shape[0]):
            for s, e in _runs(axis_view[i]):
                if e - s > limit:
                    axis_view[i, s:e] = False
    inner = ink.shape[1]
    strips = []
    for k in range(STRIPS):
        centre = int((k + 0.5) * inner / STRIPS)
        half = max(3, int(0.015 * inner))
        band = ink[:, max(0, centre - half):min(inner, centre + half)]
        rows = band.sum(axis=1) > max(1, 0.02 * band.shape[1])
        merged: list[list[int]] = []
        for a, b in _runs(rows):
            if merged and a - merged[-1][1] <= 2:
                merged[-1][1] = b
            else:
                merged.append([a, b])
        if merged:
            median = statistics.median(b - a for a, b in merged)
            merged = [m for m in merged if m[1] - m[0] >= 0.4 * median]
        strips.append((centre + bx, len(merged)))
    return strips


def proxy_ratio(lines: list[dict], strips: list[tuple[int, int]]) -> float | None:
    """Lines crossing each strip with text, over the proxy's rows there, pooled over those strips."""
    live = [(x, rows) for x, rows in strips if rows > 0]
    if not live:
        return None
    crossed = sum(sum(1 for line in lines if line["polygon"][0][0] <= x <= line["polygon"][1][0]) for x, _ in live)
    return crossed / sum(rows for _, rows in live)


def accept_page(lines: list[dict], ratio: float | None, rules: dict = FILTER) -> str | None:
    """None to keep the page, or the reason it is rejected."""
    if len(lines) < rules["min_lines"]:
        return "too_few_lines"
    low, high = rules["proxy_ratio"]
    if ratio is None or not low <= ratio <= high:
        return "disagrees_with_proxy"
    return None


def source_key(source: dict) -> str:
    """The book a page belongs to: its Wikisource `index_key`, or a `work_key` for other sources. Required."""
    key = (source or {}).get("index_key") or (source or {}).get("work_key")
    if not isinstance(key, str) or not key.strip():
        raise EngineError("Every real page needs a non-empty index_key or work_key")
    return key


def check_source(source: dict, eval_indexes: set[str]) -> str:
    """Fail closed unless the page's book is keyed, outside the evaluation Indexes, and admitted by the PD gate."""
    key = source_key(source)
    if key in eval_indexes or source.get("index_key") in eval_indexes:
        raise EngineError(f"{key} is an evaluation Index and must not be used")
    if source.get("gate_admitted") is not True:
        raise EngineError(f"{key}: its public-domain gate is not admitted")
    return key


def _tesseract_info(tesseract: Path, tessdata: Path, language: str) -> dict:
    version = run_process([str(tesseract), "--version"], 60, name="tesseract").decode("utf-8", "replace")
    traineddata = tessdata / f"{language}.traineddata"
    return {"tool": "tesseract", "version": version.splitlines()[0].strip() if version else None,
            "executable_sha256": digest(read_limited(tesseract, 200_000_000)), "language": language,
            "traineddata_sha256": digest(read_limited(traineddata, 200_000_000)),
            # tesseract-ocr/tessdata_fast and tessdata ship under Apache-2.0.
            "traineddata_licence": "Apache-2.0"}


def pseudo_label_pages(scans: Path, tesseract: Path, tessdata: Path, *, language: str = "heb", psm: int = 3,
                       rules: dict = FILTER, timeout: float = 300) -> dict:
    """Pseudo-label every used scan in `scans`/provenance.json and return the heocr_real_pages.v1 manifest."""
    provenance_raw = read_limited(scans / "provenance.json", MAX_MANIFEST_BYTES)
    provenance = json.loads(provenance_raw)
    if provenance.get("schema") not in (SCAN_PROVENANCE_SCHEMA, "heocr_r4f_scan_provenance.v1"):
        raise EngineError("Unknown scan provenance schema")
    exclusions = provenance.get("exclusions") or {"eval_indexes": provenance.get("excluded_e2d3d_indexes")}
    if not exclusions.get("eval_indexes"):
        raise EngineError("The scan provenance must list the evaluation Indexes it excludes")
    eval_indexes = set(exclusions["eval_indexes"])
    label_source = {**_tesseract_info(tesseract, tessdata, language), "psm": psm, "output": "hocr",
                    "line_classes": list(LINE_CLASSES), "line_polygon": "unpadded line bounding box",
                    "baseline": "hOCR baseline, clamped to the line box", "regions": "ocr_carea blocks as body"}
    pages, rejected = [], []
    for key, entry in sorted(provenance["files"].items()):
        if entry.get("skipped"):
            continue
        source = {name: entry.get(name) for name in ("index_key", "index_title", "commons_title", "description_url",
                                                      "file_page_revision_id", "pinned_sha1", "licence_templates",
                                                      "work_group")}
        source["gate_admitted"] = (entry.get("gate") or {}).get("admitted")
        check_source(source, eval_indexes)
        split = {"train": "train", "dev": "validation"}[entry["split"]]
        for image in entry["images"]:
            for variant in image.get("variants", []):
                if variant["file"] not in image.get("use", []):
                    continue
                relative = PurePosixPath(variant["file"])
                if relative.is_absolute() or ".." in relative.parts:
                    raise EngineError("Scan file paths must be relative and inside the scan folder")
                raw = read_limited(scans / relative, MAX_IMAGE_BYTES)
                if digest(raw) != variant["sha256"]:
                    raise EngineError("A scan does not match its recorded sha256")
                width, height = inspect_image(raw)
                hocr = run_process([str(tesseract), str(scans / relative), "-", "-l", language, "--psm", str(psm),
                                    "--tessdata-dir", str(tessdata), "hocr"], timeout, name="tesseract")
                lines, regions, stats = hocr_lines(hocr.decode("utf-8", "replace"), width, height, rules)
                ratio = proxy_ratio(lines, strip_proxy(raw))
                stats["proxy_ratio"] = None if ratio is None else round(ratio, 3)
                record = {"image": str(relative), "image_sha256": variant["sha256"], "width": width, "height": height,
                          "split": split, "source": {**source, "page": image["page"], "render_url": image.get("url"),
                                                     "variant_width": variant["width"],
                                                     "variant_derived": variant.get("derived")},
                          "stats": stats}
                reason = accept_page(lines, ratio, rules)
                if reason:
                    rejected.append({**record, "reason": reason})
                    continue
                pages.append({**record, "page_id": f"real:{key}:p{image['page']:04d}:w{width}",
                              "lines": [{name: line[name] for name in ("line_index", "region_index", "polygon",
                                                                        "baseline", "tesseract_class")}
                                        for line in lines],
                              "regions": [{name: region[name] for name in ("region_index", "type", "polygon",
                                                                            "line_indices")} for region in regions]})
    return {"schema": REAL_PAGES_SCHEMA, "scan_provenance_sha256": digest(provenance_raw),
            "label_source": label_source, "filter": rules, "exclusions": exclusions,
            "pages": pages, "rejected": rejected}


def _points(points, width: int, height: int) -> list[tuple[int, int]]:
    if not isinstance(points, list) or len(points) < 2:
        raise EngineError("Invalid real page geometry")
    out = []
    for point in points:
        if (not isinstance(point, (list, tuple)) or len(point) != 2
                or not all(isinstance(v, int) and not isinstance(v, bool) for v in point)
                or not (0 <= point[0] <= width and 0 <= point[1] <= height)):
            raise EngineError("Invalid real page geometry")
        out.append((point[0], point[1]))
    return out


def load_real_pages(manifest: Path) -> tuple[list[dict], str, dict]:
    """The manifest's pages in the shape prepare_kraken_data writes (with a `path`), its sha256, and its header.

    Every image must match its sha256 and size, every line must sit in exactly one region that contains its box, and
    the manifest must state its label source and the evaluation Indexes it excludes.
    """
    raw = read_limited(manifest, MAX_MANIFEST_BYTES)
    document = json.loads(raw)
    if not isinstance(document, dict) or document.get("schema") != REAL_PAGES_SCHEMA:
        raise EngineError("Real pages must be a " + REAL_PAGES_SCHEMA + " manifest")
    label = document.get("label_source")
    if (not isinstance(label, dict) or not HEX64.fullmatch(str(label.get("traineddata_sha256")))
            or not label.get("traineddata_licence") or not label.get("tool")):
        raise EngineError("The real pages manifest must state its label source, traineddata hash and licence")
    if not (document.get("exclusions") or {}).get("eval_indexes"):
        raise EngineError("The real pages manifest must list the evaluation Indexes it excludes")
    eval_indexes = set(document["exclusions"]["eval_indexes"])
    root = manifest.parent
    pages = []
    for entry in document.get("pages") or []:
        relative = PurePosixPath(str(entry.get("image")))
        if relative.is_absolute() or ".." in relative.parts:
            raise EngineError("Real page images must be relative paths inside the manifest's folder")
        path = root / relative
        image = read_limited(path, MAX_IMAGE_BYTES)
        width, height = entry.get("width"), entry.get("height")
        if digest(image) != entry.get("image_sha256") or inspect_image(image) != (width, height):
            raise EngineError("A real page image does not match the manifest")
        if entry.get("split") not in ("train", "validation"):
            raise EngineError("Real page splits must be train or validation")
        key = check_source(entry.get("source") or {}, eval_indexes)
        lines = []
        for position, line in enumerate(entry.get("lines") or []):
            if line.get("line_index") != position:
                raise EngineError("Real page lines must be numbered in order")
            lines.append({"line_index": position, "region": REGION_TYPE, "region_index": line.get("region_index"),
                          "polygon": _points(line.get("polygon"), width, height),
                          "baseline": _points(line.get("baseline"), width, height), "text": "",
                          "logical_line_index": None, "occluded": False})
        regions, owner = [], {}
        for position, region in enumerate(entry.get("regions") or []):
            polygon = _points(region.get("polygon"), width, height)
            if region.get("region_index") != position or region.get("type") != REGION_TYPE:
                raise EngineError("Real page regions must be numbered body regions")
            xs, ys = [x for x, _ in polygon], [y for _, y in polygon]
            for index in region.get("line_indices") or []:
                if not isinstance(index, int) or not 0 <= index < len(lines) or index in owner:
                    raise EngineError("Each real page line must be in exactly one region")
                owner[index] = position
                if lines[index]["region_index"] != position or not all(
                        min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys) for x, y in lines[index]["polygon"]):
                    raise EngineError("A real page region does not contain its line")
            regions.append({"type": REGION_TYPE, "polygon": polygon, "line_indices": list(region["line_indices"])})
        if sorted(owner) != list(range(len(lines))) or not lines:
            raise EngineError("Each real page needs lines, each in exactly one region")
        pages.append({"sample_id": entry["page_id"], "page_id": entry["page_id"], "page_sha256": digest(image),
                      "width": width, "height": height, "lines": lines, "regions": regions, "path": path,
                      "template_id": "real_page", "split": entry["split"], "source": entry["source"], "key": key})
    if not pages:
        raise EngineError("The real pages manifest has no pages")
    if len({page["page_sha256"] for page in pages}) != len(pages):
        raise EngineError("Duplicate real page image")
    by_split = [{page["key"] for page in pages if page["split"] == split} for split in ("train", "validation")]
    if by_split[0] & by_split[1]:
        raise EngineError("An Index has pages in both the train and the validation split")
    header = {name: document[name] for name in ("label_source", "filter", "exclusions") if name in document}
    reasons: dict[str, int] = {}
    for rejected in document.get("rejected") or []:
        reasons[str(rejected.get("reason"))] = reasons.get(str(rejected.get("reason")), 0) + 1
    header["rejected_by_reason"] = dict(sorted(reasons.items()))
    return pages, digest(raw), header


def real_pages_summary(pages: list[dict], manifest_sha256: str, header: dict) -> dict:
    """The path-free record of the real pages: label source, exclusions, licences and counts per split."""
    licences: dict[str, int] = {}
    files = {page["source"].get("commons_title") for page in pages}
    for title in files:
        templates = next(page["source"].get("licence_templates") for page in pages
                         if page["source"].get("commons_title") == title) or []
        key = " / ".join(templates) or "unknown"
        licences[key] = licences.get(key, 0) + 1
    exclusions = header.get("exclusions", {})
    return {"schema": REAL_PAGES_SCHEMA, "manifest_sha256": manifest_sha256,
            "label_source": header.get("label_source"), "filter": header.get("filter"),
            "exclusions": {"eval_indexes": sorted(exclusions.get("eval_indexes") or []),
                           **{name: value for name, value in exclusions.items() if name != "eval_indexes"}},
            "files": len(files), "indexes": sorted({page["key"] for page in pages}),
            "rejected_by_reason": header.get("rejected_by_reason", {}),
            "file_licence_templates": dict(sorted(licences.items())),
            **{split: {"pages": sum(page["split"] == split for page in pages),
                       "lines": sum(len(page["lines"]) for page in pages if page["split"] == split),
                       # Fixed before training, by whole work: an Index is in exactly one split.
                       "indexes": sorted({page["key"] for page in pages if page["split"] == split})}
               for split in ("train", "validation")}}


def check_real_pages_record(real: dict) -> list[str]:
    """Problems with a training record's `data.real_pages`; empty means valid."""
    problems = []
    if not isinstance(real, dict) or real.get("schema") != REAL_PAGES_SCHEMA:
        return ["data.real_pages must be a " + REAL_PAGES_SCHEMA + " summary"]
    if not HEX64.fullmatch(str(real.get("manifest_sha256"))):
        problems.append("data.real_pages.manifest_sha256 must be 64 lowercase hex characters")
    label = real.get("label_source")
    if (not isinstance(label, dict) or not HEX64.fullmatch(str(label.get("traineddata_sha256")))
            or not label.get("traineddata_licence")):
        problems.append("data.real_pages.label_source must state the traineddata hash and licence")
    if not (real.get("exclusions") or {}).get("eval_indexes"):
        problems.append("data.real_pages.exclusions.eval_indexes must list the excluded evaluation Indexes")
    for split in ("train", "validation"):
        counts = real.get(split)
        if not isinstance(counts, dict) or not all(isinstance(counts.get(k), int) and counts[k] >= 0
                                                   for k in ("pages", "lines")):
            problems.append(f"data.real_pages.{split} must count pages and lines")
    splits = [set((real.get(split) or {}).get("indexes") or []) for split in ("train", "validation")]
    if splits[0] & splits[1]:
        problems.append("data.real_pages: an Index is in both the train and the validation split")
    if (splits[0] | splits[1]) & set((real.get("exclusions") or {}).get("eval_indexes") or []):
        problems.append("data.real_pages: an evaluation Index is among the training pages")
    return problems
