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
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError

from heocr_engine.contract import SCHEMA_ID

MAX_BYTES = 50_000_000
MAX_PIXELS = 40_000_000
LANGUAGE = re.compile(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)*\Z")


class EngineError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_process(args: list[str], timeout: float, stdin: bytes | None = None,
                name: str = "Subprocess", log: BinaryIO | None = None,
                env: dict[str, str] | None = None) -> bytes:
    """Run a command and return stdout; failures fail closed and are reported under `name`.

    With `log`, stdout and stderr both go to that file instead and the result is empty.
    `env` adds variables to the inherited environment.
    """
    try:
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL if stdin is None else subprocess.PIPE,
                                   stdout=subprocess.PIPE if log is None else log,
                                   stderr=subprocess.PIPE if log is None else subprocess.STDOUT,
                                   env=None if env is None else {**os.environ, **env},
                                   start_new_session=True)
    except OSError as exc:
        raise EngineError(f"Could not start {name}") from exc
    try:
        stdout, _ = process.communicate(input=stdin, timeout=timeout)
    except BaseException as exc:
        # Reap the child and its process group on timeout or interruption.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        if isinstance(exc, subprocess.TimeoutExpired):
            raise EngineError(f"{name} timed out") from exc
        raise
    if process.returncode != 0:
        raise EngineError(f"{name} failed with exit status {process.returncode}")
    return stdout or b""


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
            if (x < 0 or y < 0 or w < 0 or h < 0 or x + w > width or y + h > height
                    or not math.isfinite(confidence) or not 0 <= confidence <= 100):
                raise ValueError("out of range")
            words.append({"text": text, "confidence": confidence, "bbox": [x, y, w, h],
                          "geometry_status": "degenerate" if w == 0 or h == 0 else "valid"})
    except (ValueError, TypeError, KeyError, csv.Error) as exc:
        raise EngineError("Invalid Tesseract word data") from exc
    return words


def inspect_image(raw: bytes) -> tuple[int, int]:
    """Validate a single-frame PNG or JPEG and return its pixel size."""
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
    return width, height


def predict(image_path: Path, executable: Path, tessdata: Path, language: str = "heb",
            psm: int = 3, timeout: float = 60) -> dict:
    raw = read_limited(image_path, MAX_BYTES)
    width, height = inspect_image(raw)
    text, words, engine = tesseract_recognize(raw, width, height, executable, tessdata,
                                              language, psm, timeout)
    sha = digest(raw)
    return {"schema_version": SCHEMA_ID, "page_id": "sha256:" + sha,
            "input": {"sha256": sha, "width": width, "height": height}, "track": "open",
            "engine": engine, "text": text, "words": words}


def tesseract_recognize(raw: bytes, width: int, height: int, executable: Path, tessdata: Path,
                        language: str = "heb", psm: int = 3,
                        timeout: float = 60) -> tuple[str, list[dict], dict]:
    if not LANGUAGE.fullmatch(language) or len(language) > 200:
        raise EngineError("Invalid language list")
    if not 0 <= psm <= 13 or psm in {0, 1, 2, 12} or not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise EngineError("Invalid or unsupported PSM, or invalid timeout")
    languages = language.split("+")
    if len(set(languages)) != len(languages):
        raise EngineError("Duplicate languages")
    executable = executable.resolve()
    tessdata = tessdata.resolve()
    executable_hash = digest(read_limited(executable, 200_000_000))
    models = [{"language": lang, "sha256": digest(read_limited(tessdata / (lang + ".traineddata"), 500_000_000))}
              for lang in languages]
    version_raw = run_process([str(executable), "--version"], timeout, name="Tesseract")
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
                     "-l", language, "--psm", str(psm), "txt", "tsv"], timeout, name="Tesseract")
        try:
            text = read_limited(target.with_suffix(".txt"), 50_000_000).decode("utf-8")
            tsv = read_limited(target.with_suffix(".tsv"), 100_000_000).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EngineError("Invalid Tesseract output encoding") from exc
    engine = {"name": "tesseract", "version": version,
              "executable_sha256": executable_hash, "models": models, "psm": psm}
    return text, parse_words(tsv, width, height), engine


def write_prediction(result: dict, output: Path) -> None:
    # Exclusive creation avoids clobbering inputs or prior predictions.
    with output.open("x", encoding="utf-8") as stream:
        try:
            json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
        except (OSError, ValueError):
            output.unlink(missing_ok=True)
            raise


def _tesseract_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="heocr-engine [tesseract]", description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--tessdata-dir", type=Path, required=True)
    parser.add_argument("--language", default="heb", help="Tesseract language codes joined by +")
    parser.add_argument("--psm", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args(argv)
    result = predict(args.image, args.executable, args.tessdata_dir, args.language, args.psm, args.timeout)
    write_prediction(result, args.output)
    return 0


def _run_main(argv: list[str]) -> int:
    from heocr_engine.stages import run_config

    parser = argparse.ArgumentParser(prog="heocr-engine run",
                                     description="Run a configured open-track stage pipeline on one image.")
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--pipeline", type=Path, required=True, help="Pipeline JSON config")
    args = parser.parse_args(argv)
    write_prediction(run_config(args.image, args.pipeline), args.output)
    return 0


def _kraken_main(argv: list[str]) -> int:
    from heocr_engine.kraken import BASE_DIRS, KrakenRecognizer
    from heocr_engine.stages import run_pipeline

    parser = argparse.ArgumentParser(prog="heocr-engine kraken",
                                     description="Run an installed kraken CLI with local models on one image.")
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--executable", type=Path, required=True, help="Path to the kraken command")
    parser.add_argument("--segmentation-model", type=Path, required=True)
    parser.add_argument("--recognition-model", type=Path, required=True)
    parser.add_argument("--base-dir", choices=BASE_DIRS, default="R",
                        help="Base text direction for reordering (default R)")
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args(argv)
    recognizer = KrakenRecognizer(args.executable, args.segmentation_model, args.recognition_model,
                                  args.base_dir, args.timeout)
    write_prediction(run_pipeline(read_limited(args.image, MAX_BYTES), recognizer), args.output)
    return 0


def _validate_main(argv: list[str]) -> int:
    from heocr_engine.validate import validate_files

    parser = argparse.ArgumentParser(prog="heocr-engine validate-predictions",
                                     description="Validate heocr_engine_prediction.v1 files.")
    parser.add_argument("predictions", type=Path, nargs="+")
    parser.add_argument("--expect-track", choices=["open", "proprietary"],
                        help="Fail any file whose track differs")
    args = parser.parse_args(argv)
    report = validate_files(args.predictions, args.expect_track)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if report["valid_count"] == report["file_count"] else 1


def _split_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("annotations", type=Path, help="hocrsyngen_line_annotations.v1 JSON")
    parser.add_argument("manifest", type=Path, help="The generation_manifest.json the annotations name")
    parser.add_argument("--validation-fraction", type=float, default=0.1,
                        help="Share of samples held out for validation (default 0.1)")
    parser.add_argument("--split-seed", type=int, default=0, help="Seed of the sample-level split (default 0)")


def _prepare_kraken_data_main(argv: list[str]) -> int:
    from heocr_engine.training import prepare_kraken_data

    parser = argparse.ArgumentParser(prog="heocr-engine prepare-kraken-data",
                                     description="Convert line annotations and page images to PAGE XML for ketos.")
    _split_args(parser)
    parser.add_argument("output", type=Path, help="New or empty output directory")
    parser.add_argument("--task", choices=["recognition", "segmentation"], default="recognition",
                        help="segmentation types each region with its hocrsyngen name (default recognition)")
    args = parser.parse_args(argv)
    summary = prepare_kraken_data(args.annotations, args.manifest, args.output, args.validation_fraction,
                                  args.split_seed, task=args.task)
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def _train_kraken_main(argv: list[str]) -> int:
    from heocr_engine.training import DEFAULT_SPEC, Hyperparameters, train_kraken

    defaults = Hyperparameters()
    parser = argparse.ArgumentParser(prog="heocr-engine train-kraken",
                                     description="Train a Kraken recognizer from scratch with local ketos "
                                                 "and write a heocr_engine_training_run.v1 record.")
    _split_args(parser)
    parser.add_argument("work_dir", type=Path, help="New or empty directory for data, checkpoints and the log")
    parser.add_argument("record", type=Path, help="Training-run record to create")
    parser.add_argument("--ketos", type=Path, required=True, help="Path to the ketos command")
    parser.add_argument("--kraken", type=Path, help="Path to the kraken command, to record its version")
    parser.add_argument("--corpus", type=Path, action="append", default=[],
                        help="Text corpus the pages were generated from, hashed into the record (repeatable)")
    parser.add_argument("--device", default="cpu", help="ketos device: cpu, mps, cuda:N or auto")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--precision", default="32-true")
    parser.add_argument("--workers", type=int, default=0,
                        help="ketos data-loader workers (default 0; kraken 7.0.2 fails with more on macOS)")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--spec", default=DEFAULT_SPEC, help="VGSL network spec (default: ketos 7.0.2 default)")
    parser.add_argument("--batch-size", type=int, default=defaults.batch_size)
    parser.add_argument("--learning-rate", type=float, default=defaults.learning_rate)
    parser.add_argument("--optimizer", default=defaults.optimizer)
    parser.add_argument("--schedule", default=defaults.schedule)
    parser.add_argument("--quit", choices=["early", "fixed"], default=defaults.quit)
    parser.add_argument("--epochs", type=int, default=defaults.epochs)
    parser.add_argument("--min-epochs", type=int, default=defaults.min_epochs)
    parser.add_argument("--lag", type=int, default=defaults.lag)
    parser.add_argument("--validation-frequency", type=float, default=defaults.validation_frequency)
    parser.add_argument("--padding", type=int, default=defaults.padding)
    parser.add_argument("--augment", action="store_true")
    parser.add_argument("--timeout", type=float, default=172_800, help="Seconds per ketos step (default 48h)")
    args = parser.parse_args(argv)
    if args.record.exists():
        raise EngineError("Record file already exists")
    hyperparameters = Hyperparameters(args.spec, args.batch_size, args.learning_rate, args.optimizer,
                                      args.schedule, args.quit, args.epochs, args.min_epochs, args.lag,
                                      args.validation_frequency, args.padding, args.augment)
    record = train_kraken(args.annotations, args.manifest, args.work_dir, args.ketos, kraken=args.kraken,
                          corpora=tuple(args.corpus), device=args.device, seed=args.seed,
                          deterministic=args.deterministic, precision=args.precision, workers=args.workers,
                          threads=args.threads, validation_fraction=args.validation_fraction,
                          split_seed=args.split_seed, hyperparameters=hyperparameters, timeout=args.timeout)
    write_prediction(record, args.record)
    return 0


def _train_kraken_seg_main(argv: list[str]) -> int:
    from heocr_engine.segmentation_training import SegmentationHyperparameters, train_kraken_segmentation

    defaults = SegmentationHyperparameters()
    parser = argparse.ArgumentParser(prog="heocr-engine train-kraken-seg",
                                     description="Train a Kraken baseline segmenter from scratch with local "
                                                 "ketos segtrain and write a heocr_engine_training_run.v1 record.")
    _split_args(parser)
    parser.add_argument("work_dir", type=Path, help="New or empty directory for data, checkpoints and the log")
    parser.add_argument("record", type=Path, help="Training-run record to create")
    parser.add_argument("--ketos", type=Path, required=True, help="Path to the ketos command")
    parser.add_argument("--kraken", type=Path, help="Path to the kraken command, to record its version")
    parser.add_argument("--corpus", type=Path, action="append", default=[],
                        help="Text corpus the pages were generated from, hashed into the record (repeatable)")
    parser.add_argument("--device", default="cpu", help="ketos device: cpu, mps, cuda:N or auto")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--deterministic", action="store_true")
    parser.add_argument("--precision", default="32-true")
    parser.add_argument("--workers", type=int, default=0, help="ketos data-loader workers (default 0)")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--spec", default=defaults.spec, help="VGSL network spec (default: ketos 7.0.2 default)")
    for name in ("learning_rate", "weight_decay", "validation_frequency", "baseline_tolerance", "dice_weight"):
        parser.add_argument("--" + name.replace("_", "-"), type=float, default=getattr(defaults, name))
    for name in ("epochs", "min_epochs", "lag", "line_width"):
        parser.add_argument("--" + name.replace("_", "-"), type=int, default=getattr(defaults, name))
    parser.add_argument("--optimizer", default=defaults.optimizer)
    parser.add_argument("--schedule", default=defaults.schedule)
    parser.add_argument("--quit", choices=["early", "fixed"], default=defaults.quit)
    parser.add_argument("--augment", action="store_true")
    parser.add_argument("--timeout", type=float, default=172_800, help="Seconds for ketos segtrain (default 48h)")
    args = parser.parse_args(argv)
    if args.record.exists():
        raise EngineError("Record file already exists")
    hyperparameters = SegmentationHyperparameters(
        args.spec, args.learning_rate, args.optimizer, args.schedule, args.weight_decay, args.quit, args.epochs,
        args.min_epochs, args.lag, args.validation_frequency, args.line_width, args.baseline_tolerance,
        args.dice_weight, args.augment)
    record = train_kraken_segmentation(
        args.annotations, args.manifest, args.work_dir, args.ketos, kraken=args.kraken, corpora=tuple(args.corpus),
        device=args.device, seed=args.seed, deterministic=args.deterministic, precision=args.precision,
        workers=args.workers, threads=args.threads, validation_fraction=args.validation_fraction,
        split_seed=args.split_seed, hyperparameters=hyperparameters, timeout=args.timeout)
    write_prediction(record, args.record)
    return 0


def _diagnose_segmentation_main(argv: list[str]) -> int:
    from heocr_engine.segmentation import METHODS, diagnose_segmentation

    parser = argparse.ArgumentParser(prog="heocr-engine diagnose-segmentation",
                                     description="Compare predicted text lines with hocrsyngen line annotations "
                                                 "(a diagnostic, not a hocrgen score).")
    parser.add_argument("annotations", type=Path, help="hocrsyngen_line_annotations.v1 JSON")
    parser.add_argument("manifest", type=Path, help="The generation_manifest.json the annotations name")
    parser.add_argument("predictions", type=Path,
                        help="Directory of <page_sha256>.xml files (PAGE XML or ALTO), one per annotated page")
    parser.add_argument("--match", choices=METHODS, default="polygon",
                        help="polygon IoU or baseline overlap (default polygon)")
    parser.add_argument("--threshold", type=float, default=0.5, help="One-to-one match threshold (default 0.5)")
    parser.add_argument("--lines", action="store_true", help="Include per-page, per-line assignments")
    parser.add_argument("--output", type=Path, help="Report file to create (default: stdout)")
    args = parser.parse_args(argv)
    report = diagnose_segmentation(args.annotations, args.manifest, args.predictions, args.match,
                                   args.threshold, args.lines)
    if args.output:
        write_prediction(report, args.output)
    else:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    return 0


COMMANDS = {"tesseract": _tesseract_main, "kraken": _kraken_main, "run": _run_main,
            "validate-predictions": _validate_main, "prepare-kraken-data": _prepare_kraken_data_main,
            "train-kraken": _train_kraken_main, "train-kraken-seg": _train_kraken_seg_main,
            "diagnose-segmentation": _diagnose_segmentation_main}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    # Without a subcommand, keep the original Tesseract command line working.
    command = COMMANDS.get(argv[0]) if argv else None
    try:
        return command(argv[1:]) if command else _tesseract_main(argv)
    except (EngineError, OSError) as exc:
        print(f"heocr-engine: {exc if isinstance(exc, EngineError) else 'Could not write output'}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
