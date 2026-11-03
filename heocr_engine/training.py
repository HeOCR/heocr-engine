"""Kraken recognizer training from hocrsyngen line annotations (docs/training_run_contract.md).

`prepare_kraken_data` turns `hocrsyngen_line_annotations.v1` plus page images into PAGE XML with
baselines and polygons, the input of `ketos compile -f page` (recognition) or `ketos segtrain -f page`
(segmentation, which also types each region). `train_kraken` runs a local ketos from scratch and returns a
path-free `heocr_engine_training_run.v1` record; heocr_engine.segmentation_training does the same for a
baseline segmenter. Nothing is downloaded or published.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import unicodedata
import xml.etree.ElementTree as ET

from heocr_engine import __version__
from heocr_engine.cli import EngineError, MAX_BYTES, digest, inspect_image, read_limited, run_process
from heocr_engine.kraken import BASE_DIRS, VERSION as KRAKEN_VERSION

ANNOTATIONS_SCHEMA = "hocrsyngen_line_annotations.v1"
TRAINING_SCHEMA_ID = "heocr_engine_training_run.v1"
PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"
# Ground truth is in logical order. ketos reorders it to display order for training (`--reorder
# --base-dir R`), and `kraken ocr --reorder --base-dir R` (heocr_engine.kraken) reorders back.
BASE_DIR = "R"
# ketos 7.0.2's default recognition network, passed explicitly so the record is complete.
DEFAULT_SPEC = ("[1,120,0,1 Cr3,13,32 Do0.1,2 Mp2,2 Cr3,13,32 Do0.1,2 Mp2,2 Cr3,9,64 Do0.1,2 Mp2,2 "
                "Cr3,9,64 Do0.1,2 S1(1x0)1,3 Lbx200 Do0.1,2 Lbx200 Do0.1,2 Lbx200 Do]")
LICENCE_STATUS = "Needs verification"
TASKS = ("recognition", "segmentation")
# Region names become kraken region types through PAGE `custom="structure {type:…;}"`, which kraken
# splits on braces, colons, semicolons and spaces.
REGION_TYPE = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")
# Segmentation regions are the sidecar's region polygons (hocrsyngen S11a) when every page has them, else
# the bounding box of each region name's line polygons.
REGION_GEOMETRIES = ("sidecar", "line_polygon_bbox")
MAX_JSON_BYTES = 500_000_000
MAX_MODEL_BYTES = 2_000_000_000
MAX_LOG_BYTES = 2_000_000_000
KETOS_VERSION = re.compile(r"ketos, version ([A-Za-z0-9.+_~-]+)")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
DEVICE = re.compile(r"(cpu|mps|auto|cuda(:[0-9]+)?)\Z")
PRECISIONS = ("16-mixed", "bf16-mixed", "32-true", "64-true")
OPTIMIZERS = ("Adam", "AdamW", "SGD", "RMSprop")
SCHEDULES = ("constant", "cosine", "exponential", "step", "1cycle", "reduceonplateau")
# Invisible bidi controls cannot be learned from pixels.
BIDI_CONTROLS = frozenset("‎‏؜‪‫‬‭‮⁦⁧⁨⁩")
FIXED_TIME = "1970-01-01T00:00:00"
BEST = re.compile(r"best_([0-9]+\.[0-9]{4})\.safetensors\Z")
CHECKPOINT = re.compile(r"checkpoint_([0-9]+)-([0-9]+\.[0-9]{4})\.ckpt\Z")
LOG_PATTERNS = {
    "lines": re.compile(r"Training set (\d+) lines, validation set (\d+) lines, alphabet (\d+) symbols"),
    "validation": re.compile(r"validation run: total chars (\d+)(?:\.0)? errors (\d+)(?:\.0)? accuracy (\S+)"),
    "early_stopping": re.compile(r"did not improve in the last \d+ records"),
    "stopping_threshold": re.compile(r"Stopping threshold reached"),
    "epoch_limit": re.compile(r"`max_epochs=\d+` reached"),
}


def _json(raw: bytes, what: str):
    try:
        return json.loads(raw.decode("utf-8"), parse_constant=lambda _: None)
    except (UnicodeDecodeError, ValueError) as exc:
        raise EngineError(f"Invalid {what} JSON") from exc


def _is_int(value, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _points(value, width: int, height: int, minimum: int) -> list[tuple[int, int]]:
    if not isinstance(value, list) or len(value) < minimum:
        raise EngineError("Invalid line geometry")
    points = []
    for point in value:
        if (not isinstance(point, list) or len(point) != 2 or not _is_int(point[0], 0, width)
                or not _is_int(point[1], 0, height)):
            raise EngineError("Invalid line geometry")
        points.append((point[0], point[1]))
    return points


def _line(line, width: int, height: int, logical_lines: int | None) -> dict:
    if not isinstance(line, dict) or not _is_int(line.get("line_index"), 0, 1_000_000):
        raise EngineError("Invalid line annotation")
    text, region = line.get("text"), line.get("region")
    if not isinstance(region, str) or not region:
        raise EngineError("Invalid line region")
    if (not isinstance(text, str) or not text or text != text.strip()
            or not unicodedata.is_normalized("NFC", text)
            or any(unicodedata.category(c) in {"Cc", "Zl", "Zp"} or c in BIDI_CONTROLS for c in text)):
        raise EngineError("Line text must be non-empty NFC text without controls or outer whitespace")
    # A physical line maps to one logical line (null for drawn text outside logical_order, such as stamps),
    # continuing it after a wrap ("space") or as a table cell ("cell").
    logical, join, occluded = line.get("logical_line_index"), line.get("logical_join"), line.get("occluded")
    if (not (logical is None or _is_int(logical, 0, (logical_lines or 1_000_001) - 1))
            or join not in (None, "space", "cell") or (logical is None and join is not None)
            or not isinstance(occluded, bool)):
        raise EngineError("Invalid logical line mapping or occlusion flag")
    baseline = _points(line.get("baseline"), width, height, 2)
    if baseline[0][0] >= baseline[-1][0] or any(a[0] > b[0] for a, b in zip(baseline, baseline[1:])):
        raise EngineError("Baselines must run left to right")
    region_index = line.get("region_index")
    if not (region_index is None or _is_int(region_index, 0, 1_000_000)):
        raise EngineError("Invalid line region index")
    return {"line_index": line["line_index"], "region": region, "region_index": region_index, "text": text,
            "polygon": _points(line.get("polygon"), width, height, 3), "baseline": baseline,
            "logical_line_index": logical, "logical_join": join, "occluded": occluded}


def _manifest_pages(manifest: dict, root: Path) -> dict[str, dict]:
    samples = manifest.get("samples") if isinstance(manifest, dict) else None
    if not isinstance(samples, list):
        raise EngineError("Invalid generation manifest")
    root = root.resolve()
    pages = {}
    for sample in samples:
        if not isinstance(sample, dict) or not isinstance(sample.get("pages"), list):
            raise EngineError("Invalid generation manifest")
        provenance = sample.get("provenance") if isinstance(sample.get("provenance"), dict) else {}
        text = sample.get("text") if isinstance(sample.get("text"), dict) else {}
        logical_order = text.get("logical_order")
        logical_lines = len(logical_order.split("\n")) if isinstance(logical_order, str) else None
        for page in sample["pages"]:
            asset = page.get("asset_path") if isinstance(page, dict) else None
            if (not isinstance(asset, str) or PurePosixPath(asset).is_absolute()
                    or ".." in PurePosixPath(asset).parts or "\\" in asset):
                raise EngineError("Invalid manifest asset path")
            path = (root / asset).resolve()
            if root not in path.parents or page.get("page_id") in pages:
                raise EngineError("Invalid manifest asset path or duplicate page")
            pages[page.get("page_id")] = {"sample_id": sample.get("sample_id"), "sha256": page.get("sha256"),
                                          "width": page.get("width"), "height": page.get("height"),
                                          "path": path, "template_id": provenance.get("template_id"),
                                          "logical_lines": logical_lines}
    return pages


def _regions(value, lines: list[dict], width: int, height: int) -> list[dict] | None:
    """Validate an optional page `regions` list: every line in exactly one region of its own type."""
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise EngineError("Invalid page regions")
    by_index = {line["line_index"]: line for line in lines}
    regions, seen = [], set()
    for number, region in enumerate(value):
        members = region.get("line_indices") if isinstance(region, dict) else None
        order = region.get("reading_order_index") if isinstance(region, dict) else None
        if (not isinstance(members, list) or region.get("region_index") != number
                or not isinstance(region.get("type"), str) or not (order is None or _is_int(order, 0, len(value) - 1))
                or not members or not all(_is_int(m, 0, 1_000_000) for m in members)
                or any(a >= b for a, b in zip(members, members[1:]))):
            raise EngineError("Invalid page regions")
        polygon = _points(region.get("polygon"), width, height, 3)
        for member in members:
            line = by_index.get(member)
            if (line is None or member in seen or line["region"] != region["type"]
                    or line.get("region_index", number) != number):
                raise EngineError("Page regions do not match their lines")
            seen.add(member)
        regions.append({"type": region["type"], "polygon": polygon, "line_indices": members})
    if seen != set(by_index):
        raise EngineError("Page regions do not match their lines")
    return regions


def load_annotated_pages(annotations: Path, manifest: Path) -> tuple[list[dict], str, str]:
    """Validate line annotations against their generation manifest and the page image bytes.

    Returns the pages sorted by (sample_id, page_id), the annotation sha256 and the manifest sha256.
    """
    annotations_raw = read_limited(annotations, MAX_JSON_BYTES)
    manifest_raw = read_limited(manifest, MAX_JSON_BYTES)
    document = _json(annotations_raw, "line annotations")
    manifest_sha = digest(manifest_raw)
    if not isinstance(document, dict) or document.get("schema") != ANNOTATIONS_SCHEMA:
        raise EngineError("Unsupported line annotation schema")
    if document.get("generation_manifest_sha256") != manifest_sha:
        raise EngineError("Line annotations do not match the generation manifest")
    if document.get("coordinate_space") != "final_page_pixels":
        raise EngineError("Unsupported coordinate space")
    assets = _manifest_pages(_json(manifest_raw, "generation manifest"), manifest.parent)
    if not isinstance(document.get("pages"), list) or not document["pages"]:
        raise EngineError("Line annotations have no pages")
    pages, seen = [], set()
    for page in document["pages"]:
        if not isinstance(page, dict):
            raise EngineError("Invalid page annotation")
        asset = assets.get(page.get("page_id"))
        sha, width, height = page.get("page_sha256"), page.get("width"), page.get("height")
        if (asset is None or page["page_id"] in seen or not isinstance(sha, str) or not HEX64.fullmatch(sha)
                or (page.get("sample_id"), sha, width, height)
                != (asset["sample_id"], asset["sha256"], asset["width"], asset["height"])):
            raise EngineError("Page annotation does not match the generation manifest")
        seen.add(page["page_id"])
        raw = read_limited(asset["path"], MAX_BYTES)
        if digest(raw) != sha or inspect_image(raw) != (width, height):
            raise EngineError("Page image does not match its annotation")
        if not isinstance(page.get("lines"), list):
            raise EngineError("Invalid page annotation")
        lines = sorted((_line(line, width, height, asset["logical_lines"]) for line in page["lines"]),
                       key=lambda x: x["line_index"])
        if len({line["line_index"] for line in lines}) != len(lines):
            raise EngineError("Duplicate line index")
        pages.append({"sample_id": page["sample_id"], "page_id": page["page_id"], "page_sha256": sha,
                      "width": width, "height": height, "lines": lines, "path": asset["path"],
                      "template_id": asset["template_id"],
                      "regions": _regions(page.get("regions"), lines, width, height)})
    if len({page["page_sha256"] for page in pages}) != len(pages):
        raise EngineError("Duplicate page image")
    return sorted(pages, key=lambda p: (p["sample_id"], p["page_id"])), digest(annotations_raw), manifest_sha


def assign_splits(sample_ids: set[str], validation_fraction: float, split_seed: int) -> dict[str, str]:
    """Split whole samples by their rank under sha256(split_seed, sample_id); input order is irrelevant."""
    if not math.isfinite(validation_fraction) or not 0 < validation_fraction <= 0.5:
        raise EngineError("Validation fraction must be in (0, 0.5]")
    if len(sample_ids) < 2:
        raise EngineError("At least two samples are needed for a train/validation split")
    ranked = sorted(sample_ids, key=lambda s: (hashlib.sha256(f"{split_seed}\0{s}".encode()).hexdigest(), s))
    count = min(max(round(len(ranked) * validation_fraction), 1), len(ranked) - 1)
    return {sample: "validation" if index < count else "train" for index, sample in enumerate(ranked)}


def _points_attr(points) -> str:
    return " ".join(f"{x},{y}" for x, y in points)


def page_regions(page: dict, sidecar: bool = False) -> list[tuple[str, list[tuple[int, int]], list[dict]]]:
    """(type, polygon, lines) per region: the sidecar regions in region_index order with `sidecar`, else one
    bounding box per annotated region name, in order of first line_index."""
    if sidecar:
        by_index = {line["line_index"]: line for line in page["lines"]}
        return [(region["type"], region["polygon"], [by_index[i] for i in region["line_indices"]])
                for region in page["regions"]]
    regions: dict[str, list[dict]] = {}
    for line in page["lines"]:
        regions.setdefault(line["region"], []).append(line)
    out = []
    for name, lines in regions.items():
        xs = [x for line in lines for x, _ in line["polygon"]]
        ys = [y for line in lines for _, y in line["polygon"]]
        out.append((name, [(min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys))], lines))
    return out


def page_xml(page: dict, image_name: str, region_types: bool = False, sidecar_regions: bool = False) -> bytes:
    """PAGE XML with one TextRegion per annotated region, lines in line_index order, right-to-left.

    With `region_types`, each region carries its hocrsyngen name as a kraken region type; with
    `sidecar_regions`, regions are the sidecar's region polygons instead of line bounding boxes.
    """
    q = lambda tag: f"{{{PAGE_NS}}}{tag}"  # noqa: E731
    root = ET.Element(q("PcGts"))
    metadata = ET.SubElement(root, q("Metadata"))
    ET.SubElement(metadata, q("Creator")).text = f"heocr-engine {__version__}"
    ET.SubElement(metadata, q("Created")).text = FIXED_TIME
    ET.SubElement(metadata, q("LastChange")).text = FIXED_TIME
    element = ET.SubElement(root, q("Page"), imageFilename=image_name, imageWidth=str(page["width"]),
                            imageHeight=str(page["height"]), readingDirection="right-to-left")
    for number, (name, box, lines) in enumerate(page_regions(page, sidecar_regions)):
        attributes = {"id": f"r{number}"}
        if region_types:
            if not REGION_TYPE.fullmatch(name):
                raise EngineError("Region names must be 1-64 ASCII letters, digits, '_' or '-' to be region types")
            attributes["custom"] = f"structure {{type:{name};}}"
        region = ET.SubElement(element, q("TextRegion"), **attributes, readingDirection="right-to-left")
        ET.SubElement(region, q("Coords"), points=_points_attr(box))
        for line in lines:
            text_line = ET.SubElement(region, q("TextLine"), id=f"l{line['line_index']}",
                                      readingDirection="right-to-left")
            ET.SubElement(text_line, q("Coords"), points=_points_attr(line["polygon"]))
            ET.SubElement(text_line, q("Baseline"), points=_points_attr(line["baseline"]))
            ET.SubElement(ET.SubElement(text_line, q("TextEquiv")), q("Unicode")).text = line["text"]
    ET.register_namespace("", PAGE_NS)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def _canonical_sha(value) -> str:
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def prepare_kraken_data(annotations: Path, manifest: Path, output: Path, validation_fraction: float = 0.1,
                        split_seed: int = 0, task: str = "recognition") -> dict:
    """Write pages/<sha256>.{jpg,png,xml}, train.txt, validation.txt and dataset.json into `output`.

    The two list files hold absolute XML paths for ketos and stay local. dataset.json is path-free.
    `task="segmentation"` types the regions and counts them per split.
    """
    if task not in TASKS:
        raise EngineError("Invalid training task")
    segmentation = task == "segmentation"
    pages, annotations_sha, manifest_sha = load_annotated_pages(annotations, manifest)
    with_regions = sum(page["regions"] is not None for page in pages)
    if segmentation and 0 < with_regions < len(pages):
        raise EngineError("Either every page or no page must have region polygons")
    # Recognition keeps line bounding boxes, so its PAGE XML does not depend on the sidecar's regions.
    sidecar = segmentation and with_regions == len(pages)
    splits = assign_splits({page["sample_id"] for page in pages}, validation_fraction, split_seed)
    if output.exists() and any(output.iterdir()):
        raise EngineError("Output directory must be new or empty")
    (output / "pages").mkdir(parents=True, exist_ok=True)
    entries, lists = [], {"train": [], "validation": []}
    for page in pages:
        raw = read_limited(page["path"], MAX_BYTES)
        if digest(raw) != page["page_sha256"]:
            raise EngineError("Page image changed while preparing data")
        suffix = ".png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else ".jpg"
        image = output / "pages" / (page["page_sha256"] + suffix)
        image.write_bytes(raw)
        xml = page_xml(page, image.name, region_types=segmentation, sidecar_regions=sidecar)
        xml_path = image.with_suffix(".xml")
        xml_path.write_bytes(xml)
        split = splits[page["sample_id"]]
        if page["lines"]:
            lists[split].append(str(xml_path.resolve()))
        entries.append({"sample_id": page["sample_id"], "page_id": page["page_id"],
                        "page_sha256": page["page_sha256"], "template_id": page["template_id"],
                        "split": split, "lines": len(page["lines"]),
                        "lines_outside_logical_order": sum(line["logical_line_index"] is None for line in page["lines"]),
                        "occluded_lines": sum(line["occluded"] for line in page["lines"]),
                        **({"regions": sorted(name for name, _, _ in page_regions(page, sidecar))}
                           if segmentation else {}),
                        "page_xml_sha256": digest(xml)})
    for split, paths in lists.items():
        if not paths:
            raise EngineError(f"The {split} split has no annotated lines")
        (output / f"{split}.txt").write_text("".join(path + "\n" for path in paths), encoding="utf-8")
    summary = {"annotation_schema": ANNOTATIONS_SCHEMA, "annotations_sha256": annotations_sha,
               "generation_manifest_sha256": manifest_sha,
               "split": {"unit": "sample", "method": "sha256_rank", "split_seed": split_seed,
                         "validation_fraction": validation_fraction, "assignment_sha256": _canonical_sha(entries)}}
    if segmentation:
        summary.update(task=task, region_geometry=REGION_GEOMETRIES[0 if sidecar else 1])
    for split in ("train", "validation"):
        chosen = [entry for entry in entries if entry["split"] == split]
        templates: dict[str, int] = {}
        for entry in chosen:
            key = entry["template_id"] if isinstance(entry["template_id"], str) else "unknown"
            templates[key] = templates.get(key, 0) + 1
        summary[split] = {"samples": len({entry["sample_id"] for entry in chosen}), "pages": len(chosen),
                          "lines": sum(entry["lines"] for entry in chosen),
                          "lines_outside_logical_order": sum(entry["lines_outside_logical_order"] for entry in chosen),
                          "occluded_lines": sum(entry["occluded_lines"] for entry in chosen),
                          "pages_by_template": dict(sorted(templates.items()))}
        if segmentation:
            regions: dict[str, int] = {}
            for entry in chosen:
                for name in entry["regions"]:
                    regions[name] = regions.get(name, 0) + 1
            summary[split]["regions_by_type"] = dict(sorted(regions.items()))
    with (output / "dataset.json").open("x", encoding="utf-8") as stream:
        json.dump({**summary, "pages": entries}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return summary


@dataclass(frozen=True)
class Hyperparameters:
    spec: str = DEFAULT_SPEC
    batch_size: int = 16
    learning_rate: float = 0.0003
    optimizer: str = "AdamW"
    schedule: str = "constant"
    quit: str = "early"
    epochs: int = -1
    min_epochs: int = 5
    lag: int = 10
    validation_frequency: float = 1.0
    padding: int = 16
    augment: bool = False

    def check(self) -> None:
        if (not isinstance(self.spec, str) or not self.spec.startswith("[") or len(self.spec) > 2000
                or not _is_int(self.batch_size, 1, 4096) or not _is_int(self.min_epochs, 0, 100_000)
                or not _is_int(self.lag, 1, 100_000) or not _is_int(self.padding, 0, 1000)
                or not math.isfinite(self.learning_rate) or not 0 < self.learning_rate < 1
                or not math.isfinite(self.validation_frequency) or not 0 < self.validation_frequency <= 100
                or self.optimizer not in OPTIMIZERS or self.schedule not in SCHEDULES
                or self.quit not in ("early", "fixed")
                or not (_is_int(self.epochs, 1, 100_000) or (self.quit == "early" and self.epochs == -1))):
            raise EngineError("Invalid training hyperparameters")

    def ketos_args(self) -> list[str]:
        return ["-s", self.spec, "-B", str(self.batch_size), "-r", repr(self.learning_rate),
                "--optimizer", self.optimizer, "--schedule", self.schedule, "-q", self.quit,
                "-N", str(self.epochs), "--min-epochs", str(self.min_epochs), "--lag", str(self.lag),
                "-F", repr(self.validation_frequency), "--pad", str(self.padding),
                "--augment" if self.augment else "--no-augment"]


def _tool_version(executable: Path, pattern: re.Pattern, name: str, timeout: float) -> str:
    try:
        match = pattern.fullmatch(run_process([str(executable), "--version"], timeout, name=name)
                                  .decode("utf-8").strip())
    except UnicodeDecodeError as exc:
        raise EngineError(f"Invalid {name} version output") from exc
    if not match:
        raise EngineError(f"Invalid {name} version output")
    return match.group(1)


def safetensors_kraken_metadata(path: Path) -> dict:
    """Read kraken's JSON metadata from a safetensors header without loading any tensors."""
    try:
        with path.open("rb") as stream:
            size = int.from_bytes(stream.read(8), "little")
            if not 0 < size <= 100_000_000:
                raise EngineError("Invalid safetensors header")
            header = json.loads(stream.read(size).decode("utf-8"))
        meta = json.loads(header["__metadata__"]["kraken_meta"])
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        raise EngineError("Invalid kraken safetensors metadata") from exc
    if not isinstance(meta, dict):
        raise EngineError("Invalid kraken safetensors metadata")
    return meta


def _check_recognition_model(meta: dict) -> None:
    models = [model for model in meta.values() if isinstance(model, dict) and "recognition" in model.get("_tasks", ())]
    if len(models) != 1 or len(meta) != 1:
        raise EngineError("Expected exactly one recognition model in the weights file")


def _scan_log(path: Path) -> dict:
    found: dict = {"stopped_by": None, "ketos_lines": None, "history": []}
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if (match := LOG_PATTERNS["lines"].search(line)):
                found["ketos_lines"] = {"train": int(match[1]), "validation": int(match[2]),
                                        "alphabet": int(match[3])}
            if (match := LOG_PATTERNS["validation"].search(line)):
                try:
                    accuracy = float(match[3])
                except ValueError as exc:
                    raise EngineError("Invalid validation line in the ketos log") from exc
                if not math.isfinite(accuracy):
                    raise EngineError("Invalid validation line in the ketos log")
                found["history"].append({"run": len(found["history"]), "chars": int(match[1]),
                                         "errors": int(match[2]), "val_accuracy": accuracy})
            for outcome in ("early_stopping", "stopping_threshold", "epoch_limit"):
                if LOG_PATTERNS[outcome].search(line):
                    found["stopped_by"] = outcome
    return found


def _stop_from_history(history: list[dict], hyperparameters, metric: str = "val_accuracy") -> str | None:
    """Replay Lightning's EarlyStopping rule on the validation history.

    ketos 7.0.2 builds EarlyStopping(monitor=metric, mode="max", patience=lag, stopping_threshold=1.0)
    without verbose=True, so a real run logs no stop message. The metric (`val_accuracy` for recognition,
    `val_mean_iu` for segmentation) cannot exceed the threshold, so only patience can stop the run: the last
    `lag` runs did not beat the best before them.
    """
    if hyperparameters.quit != "early" or not history:
        return None
    best, wait = -math.inf, 0
    for row in history:
        if row[metric] > best:
            best, wait = row[metric], 0
        else:
            wait += 1
    if wait >= hyperparameters.lag:
        return "early_stopping"
    if (hyperparameters.epochs > 0 and hyperparameters.validation_frequency == 1
            and len(history) == hyperparameters.epochs):
        return "epoch_limit"
    return None


def _portable(args: list[str], tokens: dict[str, str]) -> list[str]:
    """Replace local paths in a command with placeholders such as <ketos> and <work>."""
    out = []
    for arg in args:
        for path, token in tokens.items():
            if arg == path or arg.startswith(path + "/"):
                arg = token + arg[len(path):]
                break
        out.append(arg)
    return out


def _has_path(value) -> bool:
    if isinstance(value, str):
        return value.startswith(("/", "~")) or bool(re.match(r"[A-Za-z]:[\\/]", value)) or "/Users/" in value
    if isinstance(value, dict):
        return any(_has_path(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_path(item) for item in value)
    return False


def validate_training_run(record: dict) -> list[str]:
    """Return the problems with a heocr_engine_training_run.v1 record; empty means valid."""
    problems = []
    if not isinstance(record, dict) or record.get("schema_version") != TRAINING_SCHEMA_ID:
        return ["schema_version must be " + TRAINING_SCHEMA_ID]
    task = record.get("task", "recognition")
    if task not in TASKS:
        return ["task must be one of " + ", ".join(TASKS)]
    # A recognizer records its bidi handling; a segmenter records its classes and inference reading order.
    task_key = "text_order" if task == "recognition" else "segmentation"
    for key in ("engine", "trainer", "init", "data", task_key, "commands", "hyperparameters",
                "run", "outcome", "output", "model_licence"):
        if key not in record:
            problems.append(f"missing {key}")
    if problems:
        return problems
    if record["init"] != "from_scratch":
        problems.append("init must be from_scratch")
    data, output = record["data"], record["output"]
    for name, value in (("data.annotations_sha256", data.get("annotations_sha256")),
                        ("data.generation_manifest_sha256", data.get("generation_manifest_sha256")),
                        ("output.model_sha256", output.get("model_sha256")),
                        *((f"data.corpora[{i}].sha256", c.get("sha256") if isinstance(c, dict) else None)
                          for i, c in enumerate(data.get("corpora", [])))):
        if not isinstance(value, str) or not HEX64.fullmatch(value):
            problems.append(f"{name} must be 64 lowercase hex characters")
    if task == "recognition":
        order = record["text_order"]
        if (order.get("ground_truth") != "logical" or order.get("training_reorder") is not True
                or order.get("base_dir") not in BASE_DIRS
                or order.get("inference_base_dir") != order.get("base_dir")):
            problems.append("text_order must reorder logical ground truth with the inference base direction")
    else:
        segmentation = record["segmentation"]
        if (not isinstance(segmentation, dict) or segmentation.get("line_location") != "baseline"
                or not isinstance(segmentation.get("class_mapping"), dict)
                or not isinstance(segmentation.get("inference"), dict)
                or not segmentation["inference"].get("reading_order")):
            problems.append("segmentation must state the line location, class mapping and inference reading order")
    commands = record["commands"]
    if not isinstance(commands, dict) or not all(isinstance(cmd, list) and all(isinstance(a, str) for a in cmd)
                                                 for cmd in commands.values()):
        problems.append("commands must map names to argument lists")
    elif any(arg in ("-i", "--load", "--resume", "--resize") for arg in commands.get("train", [])):
        problems.append("a from-scratch run must not load weights")
    if not isinstance(record["model_licence"], dict) or not record["model_licence"].get("status"):
        problems.append("model_licence.status is required")
    if _has_path(record):
        problems.append("records must not contain local paths")
    return problems


def train_kraken(annotations: Path, manifest: Path, work: Path, ketos: Path, *, kraken: Path | None = None,
                 corpora: tuple[Path, ...] = (), device: str = "cpu", seed: int = 42,
                 deterministic: bool = False, precision: str = "32-true", workers: int = 0, threads: int = 1,
                 validation_fraction: float = 0.1, split_seed: int = 0,
                 hyperparameters: Hyperparameters = Hyperparameters(), timeout: float = 172_800) -> dict:
    """Prepare data, compile it, train a recognizer from scratch with local ketos, and describe the run."""
    hyperparameters.check()
    if (not DEVICE.fullmatch(device) or precision not in PRECISIONS or not _is_int(seed, 0, 2**32 - 1)
            or not _is_int(workers, 0, 256) or not _is_int(threads, 1, 256)
            or not math.isfinite(timeout) or not 0 < timeout <= 30 * 86_400):
        raise EngineError("Invalid training run settings")
    ketos = ketos.resolve()
    trainer = {"name": "ketos", "version": _tool_version(ketos, KETOS_VERSION, "ketos", 60),
               "executable_sha256": digest(read_limited(ketos, 200_000_000)),
               "kraken_version": None, "kraken_executable_sha256": None}
    if kraken is not None:
        kraken = kraken.resolve()
        trainer["kraken_version"] = _tool_version(kraken, KRAKEN_VERSION, "Kraken", 60)
        trainer["kraken_executable_sha256"] = digest(read_limited(kraken, 200_000_000))
    corpus_records = [{"sha256": digest(raw), "bytes": len(raw)}
                      for raw in (read_limited(path, MAX_JSON_BYTES) for path in corpora)]
    if work.exists() and any(work.iterdir()):
        raise EngineError("Work directory must be new or empty")
    work.mkdir(parents=True, exist_ok=True)
    work = work.resolve()
    summary = prepare_kraken_data(annotations, manifest, work / "data", validation_fraction, split_seed)
    global_args = ["--workers", str(workers), "--threads", str(threads)]
    commands = {f"compile_{split}": [str(ketos), *global_args, "compile", "-f", "page",
                                     "-o", str(work / f"{split}.arrow"), "-F", str(work / "data" / f"{split}.txt")]
                for split in ("train", "validation")}
    (work / "validation_datasets.txt").write_text(str(work / "validation.arrow") + "\n", encoding="utf-8")
    commands["train"] = [str(ketos), "-v", "-d", device, "-s", str(seed),
                         "--deterministic" if deterministic else "--no-deterministic", "--precision", precision,
                         *global_args, "train", "-f", "binary", "-o", str(work / "checkpoints"),
                         "--weights-format", "safetensors", "--reorder", "--base-dir", BASE_DIR,
                         *hyperparameters.ketos_args(), "-e", str(work / "validation_datasets.txt"),
                         str(work / "train.arrow")]
    # PyTorch has no MPS kernel for CTC loss; the fallback runs that operator on the CPU.
    environment = {"PYTORCH_ENABLE_MPS_FALLBACK": "1"} if device == "mps" else {}
    log = work / "ketos.log"
    with log.open("ab") as stream:
        for name in ("compile_train", "compile_validation", "train"):
            stream.write(f"# heocr-engine: {name}\n".encode())
            stream.flush()
            # A wide virtual terminal stops ketos's rich logger from wrapping the lines _scan_log reads.
            run_process(commands[name], timeout, name="ketos", log=stream,
                        env={"COLUMNS": "1000", **environment})
    if log.stat().st_size > MAX_LOG_BYTES:
        raise EngineError("ketos log exceeds the size limit")
    best = [path for path in (work / "checkpoints").glob("best_*.safetensors") if BEST.fullmatch(path.name)]
    if len(best) != 1:
        raise EngineError("ketos did not write exactly one best model")
    model = read_limited(best[0], MAX_MODEL_BYTES)
    _check_recognition_model(safetensors_kraken_metadata(best[0]))
    score_text = BEST.fullmatch(best[0].name)[1]
    # ketos keeps the 10 best checkpoints, named by epoch and val_accuracy; the earliest at the best score.
    best_epochs = [int(match[1]) for path in (work / "checkpoints").glob("checkpoint_*.ckpt")
                   if (match := CHECKPOINT.fullmatch(path.name)) and match[2] == score_text]
    scanned = _scan_log(log)
    history = scanned["history"]
    stopped_by = ("epoch_limit" if hyperparameters.quit == "fixed" else scanned["stopped_by"]
                  or _stop_from_history(history, hyperparameters) or "unknown")
    expected = {"train": summary["train"]["lines"], "validation": summary["validation"]["lines"]}
    tokens = {str(ketos): "<ketos>", str(work): "<work>"}
    record = {
        "schema_version": TRAINING_SCHEMA_ID,
        "engine": {"name": "heocr-engine", "version": __version__},
        "trainer": trainer,
        "task": "recognition",
        "init": "from_scratch",
        "data": {**summary, "corpora": corpus_records},
        "text_order": {"ground_truth": "logical", "training_reorder": True, "base_dir": BASE_DIR,
                       "inference_reorder": True, "inference_base_dir": BASE_DIR},
        "commands": {name: _portable(args, tokens) for name, args in commands.items()},
        "hyperparameters": asdict(hyperparameters),
        "run": {"seed": seed, "deterministic": deterministic, "device": device, "precision": precision,
                "workers": workers, "threads": threads, "environment": environment},
        "outcome": {"quit": hyperparameters.quit, "stopped_by": stopped_by,
                    "best_epoch": min(best_epochs) if best_epochs else None,
                    "validation_runs": len(history),
                    "epochs_completed": len(history) if hyperparameters.validation_frequency == 1 else None,
                    "validation_metric": {"name": "val_accuracy", "best": float(score_text),
                                          "definition": "ketos character accuracy (1 - CER) on the validation "
                                                        "split, display order, kraken-internal; not hocrgen primary.v1"},
                    "validation_history": history,
                    "ketos_reported_lines": scanned["ketos_lines"],
                    "lines_dropped_by_ketos": (None if scanned["ketos_lines"] is None else
                                               {split: expected[split] - scanned["ketos_lines"][split]
                                                for split in expected})},
        "output": {"model_sha256": digest(model), "bytes": len(model), "file_name": best[0].name,
                   "weights_format": "safetensors", "byte_reproducible": False},
        "model_licence": {"status": LICENCE_STATUS, "owner": "maintainer",
                          "basis": "planning/decisions/0007-first-trained-recognizer.md",
                          "published": False},
    }
    problems = validate_training_run(record)
    if problems:
        raise EngineError("Invalid training run record: " + "; ".join(problems))
    return record
