"""Line segmentation diagnostic against hocrsyngen line annotations (docs/segmentation_diagnostic.md).

`diagnose_segmentation` compares predicted text lines (PAGE XML or ALTO, one file per page) with the
annotated lines of a hocrsyngen batch: one-to-one detection precision, recall and F1, split, merged,
missed and spurious lines, and reading order over the matched lines. It is a diagnostic, not a
hocrgen score: it measures line geometry and order only, never text.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops, ImageDraw

from heocr_engine.cli import EngineError, digest, read_limited
from heocr_engine.training import load_annotated_pages

SCHEMA_ID = "heocr_engine_segmentation_diagnostic.v1"
METHODS = ("polygon", "baseline")
GOLD_CATEGORIES = ("matched", "split", "merged", "partial", "missed")
PREDICTED_CATEGORIES = ("matched", "merged", "fragment", "partial", "spurious")
# Non-exclusive counts: a matched line can also take part in a split or a merge.
EVENTS = ("split_gold_lines", "split_fragments", "merging_predicted_lines", "merged_gold_lines")
# A predicted line "lies in" a gold line, or "covers" it, when that share of it overlaps the other.
PART_THRESHOLD = 0.5
# Baseline matching: the mean vertical gap must stay within this share of the gold line's polygon height.
BASELINE_TOLERANCE = 0.5
BASELINE_SAMPLES = 11
MAX_XML_BYTES = 50_000_000
MAX_LINES = 10_000
NUMBER = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")
NOTE = ("Diagnostic only, not a hocrgen score: line geometry and reading order against "
        "hocrsyngen_line_annotations.v1; recognized text is not compared.")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element, name: str) -> list:
    return [child for child in element if _local(child.tag) == name]


def _numbers(text: str | None) -> list[float]:
    values = NUMBER.findall(text or "")
    if len(values) % 2 or len(values) > 20_000:
        raise EngineError("Invalid predicted line coordinates")
    return [float(value) for value in values]


def _pairs(text: str | None, width: int, height: int) -> list[tuple[int, int]]:
    values = _numbers(text)
    # Coordinates are clamped to the page; segmenters may emit points just outside it.
    return [(min(max(round(x), 0), width), min(max(round(y), 0), height)) for x, y in zip(values[::2], values[1::2])]


def _line_record(polygon, baseline, text: str) -> dict:
    return {"polygon": polygon if len(polygon) >= 3 else None,
            "baseline": baseline if len(baseline) >= 2 else None, "text": text}


def _read_kraken_geometry(raw: bytes, width: int, height: int) -> list[dict]:
    """Lines of a `--api python` geometry file (heocr_engine_kraken_geometry.v1), in its emitted order."""
    from heocr_engine.kraken_api import GEOMETRY_SCHEMA

    try:
        geometry = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EngineError("Invalid kraken geometry JSON") from exc
    if not isinstance(geometry, dict) or geometry.get("schema_version") != GEOMETRY_SCHEMA \
            or geometry.get("unit") != "pixel" or not isinstance(geometry.get("lines"), list):
        raise EngineError(f"Geometry files must be {GEOMETRY_SCHEMA} in pixels")
    if (geometry.get("width"), geometry.get("height")) != (width, height):
        raise EngineError("Geometry page size differs from the annotated page")
    lines = geometry["lines"]
    if [line.get("order") if isinstance(line, dict) else None for line in lines] != list(range(len(lines))):
        raise EngineError("Geometry lines must be listed in their order 0..n-1")

    def pairs(points) -> list[tuple[int, int]]:
        if not isinstance(points, list) or len(points) > 10_000 or not all(
                isinstance(p, list) and len(p) == 2 and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                                            for v in p) for p in points):
            raise EngineError("Invalid kraken geometry coordinates")
        return [(min(max(round(x), 0), width), min(max(round(y), 0), height)) for x, y in points]

    return [_line_record(pairs(line.get("boundary")), pairs(line.get("baseline")), str(line.get("text", "")))
            for line in lines]


def read_predicted_lines(path: Path, width: int, height: int) -> tuple[str, list[dict]]:
    """Return the format ("page", "alto" or "kraken-geometry") and the text lines in reading order.

    Each line has `polygon` and `baseline` (lists of (x, y) or None when absent) and its `text`.
    Document order (XML) or the geometry's line order (JSON) is taken as the predicted reading order.
    """
    raw = read_limited(path, MAX_XML_BYTES)
    if path.suffix == ".json":
        lines = _read_kraken_geometry(raw, width, height)
        if len(lines) > MAX_LINES:
            raise EngineError("Too many predicted lines")
        return "kraken-geometry", lines
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise EngineError("Predicted line files must not declare a DOCTYPE or entities")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise EngineError("Invalid predicted line XML") from exc
    kind = _local(root.tag)
    lines = []
    if kind == "PcGts":
        for line in root.iter():
            if _local(line.tag) != "TextLine":
                continue
            coords, base = _children(line, "Coords"), _children(line, "Baseline")
            equiv = _children(line, "TextEquiv")
            text = "".join(u.text or "" for e in equiv[:1] for u in _children(e, "Unicode"))
            lines.append(_line_record(_pairs(coords[0].get("points") if coords else None, width, height),
                                      _pairs(base[0].get("points") if base else None, width, height), text))
        kind = "page"
    elif kind == "alto":
        for line in root.iter():
            if _local(line.tag) != "TextLine":
                continue
            shapes = [p for s in _children(line, "Shape") for p in _children(s, "Polygon")]
            polygon = _pairs(shapes[0].get("POINTS"), width, height) if shapes else []
            if not polygon and all(line.get(k) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")):
                x, y, w, h = (float(line.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))
                polygon = _pairs(f"{x} {y} {x + w} {y} {x + w} {y + h} {x} {y + h}", width, height)
            text = " ".join(s.get("CONTENT", "") for s in _children(line, "String"))
            lines.append(_line_record(polygon, _pairs(line.get("BASELINE"), width, height), text))
        kind = "alto"
    else:
        raise EngineError("Predicted lines must be PAGE XML or ALTO")
    if len(lines) > MAX_LINES:
        raise EngineError("Too many predicted lines")
    return kind, lines


class _Mask:
    """A filled polygon rasterized in page pixels (even-odd fill, boundary included)."""

    def __init__(self, points):
        xs, ys = [x for x, _ in points], [y for _, y in points]
        self.box = (min(xs), min(ys), max(xs) + 1, max(ys) + 1)
        self.image = Image.new("1", (self.box[2] - self.box[0], self.box[3] - self.box[1]), 0)
        ImageDraw.Draw(self.image).polygon([(x - self.box[0], y - self.box[1]) for x, y in points],
                                           fill=255, outline=255)
        self.area = self.image.histogram()[255]

    def intersection(self, other: "_Mask") -> int:
        x0, y0 = max(self.box[0], other.box[0]), max(self.box[1], other.box[1])
        x1, y1 = min(self.box[2], other.box[2]), min(self.box[3], other.box[3])
        if x0 >= x1 or y0 >= y1:
            return 0
        crop = lambda m: m.image.crop((x0 - m.box[0], y0 - m.box[1], x1 - m.box[0], y1 - m.box[1]))  # noqa: E731
        return ImageChops.logical_and(crop(self), crop(other)).histogram()[255]


def _polygon_overlaps(gold: list[dict], predicted: list[dict]) -> dict:
    gold_masks = [_Mask(line["polygon"]) for line in gold]
    overlaps = {}
    for j, line in enumerate(predicted):
        if line["polygon"] is None:
            continue
        mask = _Mask(line["polygon"])
        for i, other in enumerate(gold_masks):
            inter = mask.intersection(other)
            if inter:
                overlaps[i, j] = (inter / (mask.area + other.area - inter), inter / mask.area, inter / other.area)
    return overlaps


def _y_at(points, x: float) -> float:
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return points[0][1] if x < points[0][0] else points[-1][1]


def _baseline_overlaps(gold: list[dict], predicted: list[dict]) -> dict:
    overlaps = {}
    for j, line in enumerate(predicted):
        if line["baseline"] is None:
            continue
        # Baselines are compared as functions of x; right-to-left point order is accepted.
        mine = sorted(line["baseline"])
        for i, other in enumerate(gold):
            theirs = other["baseline"]
            lo, hi = max(mine[0][0], theirs[0][0]), min(mine[-1][0], theirs[-1][0])
            if hi <= lo:
                continue
            xs = [lo + (hi - lo) * k / (BASELINE_SAMPLES - 1) for k in range(BASELINE_SAMPLES)]
            gap = sum(abs(_y_at(mine, x) - _y_at(theirs, x)) for x in xs) / len(xs)
            ys = [y for _, y in other["polygon"]]
            if gap > BASELINE_TOLERANCE * max(max(ys) - min(ys), 1):
                continue
            length_p, length_g = mine[-1][0] - mine[0][0], theirs[-1][0] - theirs[0][0]
            overlap = hi - lo
            overlaps[i, j] = (overlap / (max(mine[-1][0], theirs[-1][0]) - min(mine[0][0], theirs[0][0])),
                              overlap / max(length_p, 1), overlap / max(length_g, 1))
    return overlaps


def gold_order(lines: list[dict]) -> list[int]:
    """Indices of gold lines in reading order: logical_line_index, then line_index; unmapped lines last."""
    return sorted(range(len(lines)), key=lambda i: (lines[i]["logical_line_index"] is None,
                                                    lines[i]["logical_line_index"] or 0, lines[i]["line_index"]))


def match_page(gold: list[dict], predicted: list[dict], method: str = "polygon", threshold: float = 0.5) -> dict:
    """Match one page's predicted lines (in predicted order) to its gold lines.

    Returns `gold` and `predicted` per-line records (category, one-to-one partner, score, and for each
    predicted line its `anchor`: the gold line it lies in most), plus order pair counts.
    """
    if method not in METHODS:
        raise EngineError("Unknown matching method")
    if not 0 < threshold <= 1:
        raise EngineError("Matching threshold must be in (0, 1]")
    overlaps = (_polygon_overlaps if method == "polygon" else _baseline_overlaps)(gold, predicted)
    gold_partner: dict[int, int] = {}
    predicted_partner: dict[int, int] = {}
    # One-to-one greedy matching by descending score; ties break on gold, then predicted index.
    for (i, j), (score, _, _) in sorted(overlaps.items(), key=lambda item: (-item[1][0], item[0])):
        if score >= threshold and i not in gold_partner and j not in predicted_partner:
            gold_partner[i], predicted_partner[j] = j, i
    lies_in = {}
    covers = {}
    for (i, j), (_, of_predicted, of_gold) in overlaps.items():
        if of_predicted >= PART_THRESHOLD:
            lies_in.setdefault(i, set()).add(j)
        if of_gold >= PART_THRESHOLD:
            covers.setdefault(j, set()).add(i)
    split_gold = {i for i, members in lies_in.items() if len(members) >= 2}
    fragments = {j for i in split_gold for j in lies_in[i]}
    merging = {j for j, golds in covers.items() if len(golds) >= 2}
    merged_gold = {i for j in merging for i in covers[j]}
    covered_gold = {i for golds in covers.values() for i in golds}
    inside_gold = {j for members in lies_in.values() for j in members}
    gold_records = []
    for i, line in enumerate(gold):
        if i in gold_partner:
            category = "matched"
        elif i in split_gold:
            category = "split"
        elif i in merged_gold:
            category = "merged"
        elif i in lies_in or i in covered_gold:
            category = "partial"
        else:
            category = "missed"
        partner = gold_partner.get(i)
        gold_records.append({"line_index": line["line_index"], "category": category, "predicted": partner,
                             "score": None if partner is None else round(overlaps[i, partner][0], 4)})
    predicted_records = []
    for j in range(len(predicted)):
        candidates = [(of_predicted, score, -i) for (i, k), (score, of_predicted, _) in overlaps.items() if k == j]
        anchor = -max(candidates)[2] if candidates else None
        if j in predicted_partner:
            category = "matched"
        elif j in merging:
            category = "merged"
        elif j in fragments:
            category = "fragment"
        elif j in covers or j in inside_gold:
            category = "partial"
        else:
            category = "spurious"
        partner = predicted_partner.get(j)
        predicted_records.append({"category": category,
                                  "gold": None if partner is None else gold[partner]["line_index"],
                                  "anchor": None if anchor is None else gold[anchor]["line_index"]})
    # Reading order over matched lines: gold rank against predicted (document) rank.
    rank = {i: r for r, i in enumerate(gold_order(gold))}
    sequence = [gold_partner[i] for i in sorted(gold_partner, key=rank.get)]
    concordant = sum(a < b for n, a in enumerate(sequence) for b in sequence[n + 1:])
    discordant = sum(a > b for n, a in enumerate(sequence) for b in sequence[n + 1:])
    adjacent_kept = sum(a < b for a, b in zip(sequence, sequence[1:]))
    return {"gold": gold_records, "predicted": predicted_records,
            "events": {"split_gold_lines": len(split_gold), "split_fragments": len(fragments),
                       "merging_predicted_lines": len(merging), "merged_gold_lines": len(merged_gold)},
            "order": {"matched_lines": len(sequence), "concordant_pairs": concordant,
                      "discordant_pairs": discordant, "adjacent_pairs": max(len(sequence) - 1, 0),
                      "adjacent_pairs_kept": adjacent_kept}}


def _empty() -> dict:
    return {"pages": 0, "gold_lines": 0, "predicted_lines": 0,
            "gold": dict.fromkeys(GOLD_CATEGORIES, 0), "predicted": dict.fromkeys(PREDICTED_CATEGORIES, 0),
            "events": dict.fromkeys(EVENTS, 0),
            "order": {"matched_lines": 0, "concordant_pairs": 0, "discordant_pairs": 0, "adjacent_pairs": 0,
                      "adjacent_pairs_kept": 0, "pages_scored": 0, "pages_in_order": 0}}


def _add(stats: dict, page: dict) -> None:
    stats["pages"] += 1
    stats["gold_lines"] += len(page["gold"])
    stats["predicted_lines"] += len(page["predicted"])
    for side in ("gold", "predicted"):
        for record in page[side]:
            stats[side][record["category"]] += 1
    for key in EVENTS:
        stats["events"][key] += page["events"][key]
    order = page["order"]
    for key in ("matched_lines", "concordant_pairs", "discordant_pairs", "adjacent_pairs", "adjacent_pairs_kept"):
        stats["order"][key] += order[key]
    if order["matched_lines"] >= 2:
        stats["order"]["pages_scored"] += 1
        stats["order"]["pages_in_order"] += order["discordant_pairs"] == 0


def _ratio(a: int, b: int):
    return round(a / b, 4) if b else None


def _finish(stats: dict) -> dict:
    matched = stats["gold"]["matched"]
    precision, recall = _ratio(matched, stats["predicted_lines"]), _ratio(matched, stats["gold_lines"])
    f1 = _ratio(2 * matched, stats["predicted_lines"] + stats["gold_lines"])
    order = stats["order"]
    order["kendall_tau"] = _ratio(order["concordant_pairs"] - order["discordant_pairs"],
                                  order["concordant_pairs"] + order["discordant_pairs"])
    order["adjacent_kept_fraction"] = _ratio(order["adjacent_pairs_kept"], order["adjacent_pairs"])
    return {**stats, "precision": precision, "recall": recall, "f1": f1}


def diagnose_segmentation(annotations: Path, manifest: Path, predictions: Path, method: str = "polygon",
                          threshold: float = 0.5, include_lines: bool = False) -> dict:
    """Score a directory of `<page_sha256>.xml` (PAGE XML or ALTO) or `<page_sha256>.json` (kraken geometry)
    predicted-line files against line annotations."""
    pages, annotations_sha, manifest_sha = load_annotated_pages(annotations, manifest)
    if not predictions.is_dir():
        raise EngineError("Predictions must be a directory")
    paths = [*predictions.glob("*.xml"), *predictions.glob("*.json")]
    files = {path.stem: path for path in paths}
    if len(files) != len(paths):
        raise EngineError("A page has both an .xml and a .json prediction file")
    expected = {page["page_sha256"] for page in pages}
    if set(files) != expected:
        raise EngineError(f"Prediction files must be exactly <page_sha256>.xml or .json for the {len(expected)} "
                          f"annotated pages ({len(expected - set(files))} missing, "
                          f"{len(set(files) - expected)} unexpected)")
    overall, by_template, formats, file_hashes, page_reports = _empty(), {}, set(), [], []
    for page in pages:
        path = files[page["page_sha256"]]
        kind, predicted = read_predicted_lines(path, page["width"], page["height"])
        formats.add(kind)
        file_hashes.append([page["page_sha256"], digest(read_limited(path, MAX_XML_BYTES))])
        result = match_page(page["lines"], predicted, method, threshold)
        template = page["template_id"] if isinstance(page["template_id"], str) else "unknown"
        _add(overall, result)
        _add(by_template.setdefault(template, _empty()), result)
        if include_lines:
            page_reports.append({"page_id": page["page_id"], "page_sha256": page["page_sha256"],
                                 "template_id": template, **result})
    report = {"schema_version": SCHEMA_ID, "diagnostic_only": True, "note": NOTE,
              "annotations_sha256": annotations_sha, "generation_manifest_sha256": manifest_sha,
              "predictions": {"format": "+".join(sorted(formats)), "files": len(file_hashes),
                              "set_sha256": digest(json.dumps(sorted(file_hashes)).encode())},
              "matching": {"method": method, "threshold": threshold, "part_threshold": PART_THRESHOLD,
                           **({"baseline_tolerance": BASELINE_TOLERANCE} if method == "baseline" else {}),
                           "one_to_one": "greedy by descending score"},
              "reading_order": {"gold": "logical_line_index, then line_index; lines outside logical_order last",
                                "predicted": ("geometry line order" if formats == {"kraken-geometry"} else
                                            "document order of TextLine elements" if "kraken-geometry" not in formats
                                            else "document order of TextLine elements, or geometry line order"),
                                "over": "one-to-one matched lines"},
              "overall": _finish(overall),
              "by_template": {name: _finish(stats) for name, stats in sorted(by_template.items())}}
    if include_lines:
        report["pages"] = page_reports
    return report
