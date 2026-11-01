"""Validate heocr_engine_prediction.v1 files, including predictions-only submissions."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re

from heocr_engine.contract import LEGACY_SCHEMA_VERSIONS, SCHEMA_ID, STAGE_KINDS, TRACKS

HEX64 = re.compile(r"[0-9a-f]{64}\Z")
# Strings that look like local filesystem locations; predictions must stay path-free.
LOCAL_PATH = re.compile(r"(\A(/|~/|[A-Za-z]:[\\/]|\\\\|file:))|(/(Users|home|tmp|private|var)/)")
MAX_FILE_BYTES = 200_000_000


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def _path_like_strings(value, where: str):
    if isinstance(value, str):
        if LOCAL_PATH.search(value):
            yield where
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _path_like_strings(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _path_like_strings(item, f"{where}[{index}]")


def _validate_stage(stage, index: int) -> list[str]:
    where = f"pipeline[{index}]"
    if not isinstance(stage, dict):
        return [f"{where} must be an object"]
    errors = []
    if stage.get("kind") not in STAGE_KINDS:
        errors.append(f"{where}.kind must be one of {', '.join(STAGE_KINDS)}")
    for key in ("name", "version"):
        if not isinstance(stage.get(key), str) or not stage.get(key):
            errors.append(f"{where}.{key} must be a non-empty string")
    if stage.get("track") not in TRACKS:
        errors.append(f"{where}.track must be open or proprietary")
    for key in ("deterministic", "requires_network"):
        if not isinstance(stage.get(key), bool):
            errors.append(f"{where}.{key} must be a boolean")
    if stage.get("track") == "open" and stage.get("requires_network") is not False:
        errors.append(f"{where} is open-track but does not declare requires_network: false")
    if "license" in stage and stage["license"] is not None and not isinstance(stage["license"], str):
        errors.append(f"{where}.license must be a string or null")
    artifacts = stage.get("artifacts", [])
    if not isinstance(artifacts, list):
        errors.append(f"{where}.artifacts must be a list")
    else:
        for number, artifact in enumerate(artifacts):
            if (not isinstance(artifact, dict) or not isinstance(artifact.get("role"), str)
                    or not HEX64.fullmatch(str(artifact.get("sha256", "")))):
                errors.append(f"{where}.artifacts[{number}] needs a role and a sha256")
    if "details" in stage and not isinstance(stage["details"], dict):
        errors.append(f"{where}.details must be an object")
    if "config_sha256" in stage and stage["config_sha256"] is not None \
            and not HEX64.fullmatch(str(stage["config_sha256"])):
        errors.append(f"{where}.config_sha256 must be 64 lowercase hex characters")
    return errors


def _validate_word(word, index: int, width: int | None, height: int | None) -> list[str]:
    where = f"words[{index}]"
    if not isinstance(word, dict):
        return [f"{where} must be an object"]
    errors = []
    if not isinstance(word.get("text"), str):
        errors.append(f"{where}.text must be a string")
    confidence = word.get("confidence")
    if confidence is not None and (not _is_number(confidence) or not 0 <= confidence <= 100):
        errors.append(f"{where}.confidence must be null or within 0-100")
    bbox = word.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4 or not all(_is_int(v) for v in bbox):
        return errors + [f"{where}.bbox must be four integers"]
    x, y, w, h = bbox
    if x < 0 or y < 0 or w < 0 or h < 0 or (width is not None and height is not None
                                            and (x + w > width or y + h > height)):
        errors.append(f"{where}.bbox lies outside the input image")
    expected = "degenerate" if w == 0 or h == 0 else "valid"
    if word.get("geometry_status") != expected:
        errors.append(f"{where}.geometry_status must be {expected}")
    return errors


def validate_prediction(record) -> tuple[list[str], dict]:
    """Return (errors, normalized summary). Legacy "1.0" files read as v1 open-track."""
    if not isinstance(record, dict):
        return ["prediction must be a JSON object"], {}
    errors = []
    version = record.get("schema_version")
    legacy = version in LEGACY_SCHEMA_VERSIONS
    if version != SCHEMA_ID and not legacy:
        errors.append(f"schema_version must be {SCHEMA_ID}")
    track = record.get("track", "open" if legacy else None)
    if track not in TRACKS:
        errors.append("track must be open or proprietary")
    width = height = None
    sha = None
    source = record.get("input")
    if not isinstance(source, dict):
        errors.append("input must be an object")
    else:
        sha = source.get("sha256")
        if not isinstance(sha, str) or not HEX64.fullmatch(sha):
            errors.append("input.sha256 must be 64 lowercase hex characters")
        if _is_int(source.get("width")) and _is_int(source.get("height")) \
                and source["width"] > 0 and source["height"] > 0:
            width, height = source["width"], source["height"]
        else:
            errors.append("input.width and input.height must be positive integers")
    if sha and record.get("page_id") != "sha256:" + sha:
        errors.append("page_id must be sha256: plus input.sha256")
    engine = record.get("engine")
    if not isinstance(engine, dict) or not all(isinstance(engine.get(key), str) and engine.get(key)
                                               for key in ("name", "version")):
        errors.append("engine must be an object with name and version strings")
    if not isinstance(record.get("text"), str):
        errors.append("text must be a string")
    words = record.get("words")
    if not isinstance(words, list):
        errors.append("words must be a list")
    else:
        for index, word in enumerate(words):
            errors.extend(_validate_word(word, index, width, height))
    pipeline = record.get("pipeline")
    if pipeline is not None:
        if legacy:
            errors.append("legacy 1.0 predictions cannot carry pipeline")
        elif not isinstance(pipeline, list) or not pipeline:
            errors.append("pipeline must be a non-empty list when present")
        else:
            for index, stage in enumerate(pipeline):
                errors.extend(_validate_stage(stage, index))
            if track == "open" and any(isinstance(stage, dict) and stage.get("track") != "open"
                                       for stage in pipeline):
                errors.append("an open-track prediction cannot contain non-open stages")
            if not any(isinstance(stage, dict) and stage.get("kind") == "recognize"
                       for stage in pipeline):
                errors.append("pipeline must contain a recognize stage")
    # Recognized text and words are content, not provenance, so they are not path-checked.
    provenance = {key: value for key, value in record.items() if key not in {"text", "words"}}
    for where in _path_like_strings(provenance, "prediction"):
        errors.append(f"{where} looks like a local filesystem path")
    summary = {"page_id": record.get("page_id"), "track": track, "legacy": legacy}
    return errors, summary


def validate_files(paths: list[Path], expect_track: str | None = None) -> dict:
    """Validate prediction files and report counts per track; open and proprietary stay separate."""
    files = []
    seen: dict[str, str] = {}
    for path in paths:
        name = path.name
        try:
            with path.open("rb") as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise ValueError("file exceeds the size limit")
            record = json.loads(data.decode("utf-8"), parse_constant=_reject_constant)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            files.append({"file": name, "valid": False, "errors": [f"unreadable prediction: {exc}"]})
            continue
        errors, summary = validate_prediction(record)
        if expect_track and summary.get("track") != expect_track:
            errors.append(f"expected track {expect_track}, found {summary.get('track')}")
        page_id = summary.get("page_id")
        if isinstance(page_id, str) and page_id in seen:
            errors.append(f"duplicate page_id also in {seen[page_id]}")
        elif isinstance(page_id, str):
            seen[page_id] = name
        files.append({"file": name, "valid": not errors, "errors": errors, **summary})
    tracks = {track: sum(1 for item in files if item["valid"] and item.get("track") == track)
              for track in TRACKS}
    return {"schema": SCHEMA_ID, "file_count": len(files),
            "valid_count": sum(1 for item in files if item["valid"]),
            "valid_by_track": tracks, "files": files}


def _reject_constant(name: str):
    raise ValueError(f"non-finite number {name}")
