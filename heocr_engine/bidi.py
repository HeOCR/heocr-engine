"""Conservative, opt-in physical-line reordering for imported predictions."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import math
import re

from heocr_engine.validate import validate_prediction
from heocr_engine.contract import SCHEMA_ID

_HEBREW = re.compile(r"[\u0590-\u05ff]")
_LATIN = re.compile(r"[A-Za-z]")
_NUMBER = re.compile(r"\d")
_NEGATION = re.compile(r"(?<!\w)[ובכלשה]*(?:לא|אין|אינו|איננו|אינה|אינם|אינן|בלי|ללא|בלתי|אסור)(?!\w)")


def _box(value, width, height):
    if not isinstance(value, list) or len(value) != 4 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in value
    ):
        raise ValueError("invalid pixel box")
    x, y, w, h = value
    if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError("pixel box outside image or degenerate")
    return x, y, x + w, y + h


def _intersects(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def correct_prediction(prediction, geometry):
    """Return (new prediction, report); never mutate the input or infer absent geometry.

    Geometry is an explicit caller-supplied observation, not reference text. See docs/stages.md.
    Invalid or missing geometry abstains for the entire page.
    """
    errors, _ = validate_prediction(prediction)
    if errors:
        raise ValueError("invalid prediction: " + errors[0])
    output = deepcopy(prediction)
    report = {"status": "abstained", "reason": "missing_or_invalid_geometry", "changed_lines": 0}
    try:
        if not isinstance(geometry, dict) or geometry.get("unit") != "pixel":
            return output, report
        lines, tables = geometry["lines"], geometry["tables"]
        if not isinstance(lines, list) or not isinstance(tables, list):
            return output, report
        width, height = prediction["input"]["width"], prediction["input"]["height"]
        table_boxes = [_box(t["bbox"], width, height) for t in tables]
        prepared = []
        for line in lines:
            text = line["text"]
            if not isinstance(text, str) or not text or "\n" in text or "\r" in text:
                raise ValueError("line must be one physical line")
            lb = _box(line["bbox"], width, height)
            words = line["words"]
            if not isinstance(words, list):
                raise ValueError("words must be a list")
            ws = []
            for word in words:
                token = word["text"]
                if not isinstance(token, str) or not token or len(token.split()) != 1 or token != token.strip():
                    raise ValueError("invalid word")
                ws.append((token, _box(word["bbox"], width, height)))
            prepared.append((text, lb, ws))
    except (KeyError, TypeError, ValueError, OverflowError):
        return output, report

    changes = []
    raw = prediction["text"]
    for text, lb, words in prepared:
        matches = list(re.finditer(r"(?<!\S)" + re.escape(text) + r"(?!\S)", raw))
        if (len(matches) != 1 or not _HEBREW.search(text) or not _LATIN.search(text)
                or _NUMBER.search(text) or _NEGATION.search(text)
                or any(_intersects(lb, table) for table in table_boxes)
                or not words or Counter(text.split()) != Counter(w[0] for w in words)):
            continue
        ordered = sorted(words, key=lambda w: -w[1][0])
        boxes = [w[1] for w in ordered]
        if any(b[0] < lb[0] - 1 or b[1] < lb[1] - 1 or b[2] > lb[2] + 1
               or b[3] > lb[3] + 1 for b in boxes):
            continue
        if any(a[0] <= b[2] for a, b in zip(boxes, boxes[1:])):
            continue
        if any(_LATIN.search(a[0]) and _LATIN.search(b[0]) for a, b in zip(ordered, ordered[1:])):
            continue
        candidate = " ".join(w[0] for w in ordered)
        if candidate != text:
            changes.append((matches[0].start(), matches[0].end(), candidate))
    changes.sort()
    if any(a[1] > b[0] for a, b in zip(changes, changes[1:])):
        report["reason"] = "overlapping_lines"
        return output, report
    for start, end, replacement in reversed(changes):
        output["text"] = output["text"][:start] + replacement + output["text"][end:]
    report = {"status": "changed" if changes else "abstained",
              "reason": "eligible_lines" if changes else "no_eligible_lines", "changed_lines": len(changes)}
    if changes:
        if not output.get("pipeline"):
            # The existing engine field remains authoritative for recognizer provenance.
            output["pipeline"] = [{"kind": "recognize", "name": output["engine"]["name"],
                "version": output["engine"]["version"], "track": output.get("track", "open"),
                "deterministic": False, "requires_network": output.get("track") == "proprietary"}]
        output["schema_version"] = SCHEMA_ID
        output.setdefault("track", "open")
        output["pipeline"].append({"kind": "postcorrect", "name": "bidi-lines",
            "version": "1", "track": "open", "deterministic": True, "requires_network": False,
            "license": "MIT", "details": {"changed_lines": len(changes), "geometry_tolerance_px": 1}})
    return output, report
