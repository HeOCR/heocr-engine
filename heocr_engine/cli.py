"""Run Tesseract on one image and write a path-free prediction."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile

from PIL import Image, UnidentifiedImageError

MAX_BYTES = 50_000_000
MAX_PIXELS = 40_000_000
LANGUAGE = re.compile(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*\Z")


class EngineError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_process(args: list[str], timeout: float) -> bytes:
    try:
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
    except OSError as exc:
        raise EngineError("Could not start Tesseract") from exc
    try:
        stdout, _ = process.communicate(timeout=timeout)
    except BaseException as exc:
        # Reap the child and its process group on timeout or interruption.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        if isinstance(exc, subprocess.TimeoutExpired):
            raise EngineError("Tesseract timed out") from exc
        raise
    if process.returncode != 0:
        raise EngineError("Tesseract failed")
    return stdout


def read_limited(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
    except OSError as exc:
        raise EngineError("Could not read a required file") from exc
    if len(data) > limit:
        raise EngineError("A required file exceeds the size limit")
    return data


def parse_words(tsv: str, width: int, height: int) -> list[dict]:
    reader = csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    required = {"level", "left", "top", "width", "height", "conf", "text"}
    if (not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames))
            or not required.issubset(reader.fieldnames)):
        raise EngineError("Invalid Tesseract TSV header")
    words = []
    try:
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("invalid row shape")
            if row["level"] not in {"1", "2", "3", "4", "5"}:
                raise ValueError("invalid level")
            if row["level"] != "5":
                continue
            text = row["text"]
            if not text:
                continue
            x, y, w, h = (int(row[key]) for key in ("left", "top", "width", "height"))
            confidence = float(row["conf"])
            if (x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height
                    or not math.isfinite(confidence) or not 0 <= confidence <= 100):
                raise ValueError("out of range")
            words.append({"text": text, "confidence": confidence, "bbox": [x, y, w, h]})
    except (ValueError, TypeError, KeyError, csv.Error) as exc:
        raise EngineError("Invalid Tesseract word data") from exc
    return words


def predict(image_path: Path, executable: Path, tessdata: Path, language: str = "heb",
            psm: int = 3, timeout: float = 60) -> dict:
    if not LANGUAGE.fullmatch(language) or len(language) > 200:
        raise EngineError("Invalid language list")
    if not 0 <= psm <= 13 or psm in {0, 1, 2, 12} or not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise EngineError("Invalid or unsupported PSM, or invalid timeout")
    languages = language.split("+")
    if len(set(languages)) != len(languages):
        raise EngineError("Duplicate languages")
    raw = read_limited(image_path, MAX_BYTES)
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {"PNG", "JPEG"} or getattr(image, "n_frames", 1) != 1:
                raise EngineError("Input must be a single PNG or JPEG image")
            width, height = image.size
            if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
                raise EngineError("Invalid image dimensions")
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise EngineError("Invalid image") from exc
    executable = executable.resolve()
    tessdata = tessdata.resolve()
    executable_hash = digest(read_limited(executable, 200_000_000))
    models = [{"language": lang, "sha256": digest(read_limited(tessdata / (lang + ".traineddata"), 500_000_000))}
              for lang in languages]
    version_raw = run_process([str(executable), "--version"], timeout)
    try:
        version = version_raw.decode("utf-8").splitlines()[0]
    except (UnicodeDecodeError, IndexError) as exc:
        raise EngineError("Invalid Tesseract version output") from exc
    if not re.fullmatch(r"tesseract [A-Za-z0-9.+_~-]+", version):
        raise EngineError("Invalid Tesseract version output")
    with tempfile.TemporaryDirectory(prefix="heocr-") as temp:
        root = Path(temp)
        source = root / ("input.png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else "input.jpg")
        source.write_bytes(raw)
        target = root / "result"
        run_process([str(executable), str(source), str(target), "--tessdata-dir", str(tessdata),
                     "-l", language, "--psm", str(psm), "txt", "tsv"], timeout)
        try:
            text = read_limited(target.with_suffix(".txt"), 50_000_000).decode("utf-8")
            tsv = read_limited(target.with_suffix(".tsv"), 100_000_000).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EngineError("Invalid Tesseract output encoding") from exc
    sha = digest(raw)
    return {"schema_version": "1.0", "page_id": "sha256:" + sha,
            "input": {"sha256": sha, "width": width, "height": height},
            "engine": {"name": "tesseract", "version": version,
                       "executable_sha256": executable_hash, "models": models, "psm": psm},
            "text": text, "words": parse_words(tsv, width, height)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--tessdata-dir", type=Path, required=True)
    parser.add_argument("--language", default="heb", help="Tesseract language codes joined by +")
    parser.add_argument("--psm", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    try:
        result = predict(args.image, args.executable, args.tessdata_dir, args.language, args.psm, args.timeout)
        # Exclusive creation avoids clobbering inputs or prior predictions.
        with args.output.open("x", encoding="utf-8") as output:
            try:
                json.dump(result, output, ensure_ascii=False, indent=2, allow_nan=False)
                output.write("\n")
                output.flush()
            except (OSError, ValueError):
                args.output.unlink(missing_ok=True)
                raise
    except (EngineError, OSError) as exc:
        print(f"heocr-engine: {exc if isinstance(exc, EngineError) else 'Could not write output'}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
