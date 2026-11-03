"""Kraken baseline segmenter training from hocrsyngen line annotations (docs/training_run_contract.md).

`train_kraken_segmentation` writes PAGE XML with typed regions (`prepare_kraken_data(task="segmentation")`),
runs a local `ketos segtrain` from scratch and returns a path-free `heocr_engine_training_run.v1` record
with `task: "segmentation"`. Nothing is downloaded or published (planning/decisions/0008).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
import re

from heocr_engine import __version__
from heocr_engine.cli import EngineError, digest, read_limited, run_process
from heocr_engine.kraken import VERSION as KRAKEN_VERSION
from heocr_engine.training import (BEST, CHECKPOINT, DEVICE, KETOS_VERSION, LICENCE_STATUS, MAX_JSON_BYTES,
                                   MAX_LOG_BYTES, MAX_MODEL_BYTES, OPTIMIZERS, PRECISIONS, SCHEDULES,
                                   TRAINING_SCHEMA_ID, _is_int, _portable, _stop_from_history, _tool_version,
                                   prepare_kraken_data, safetensors_kraken_metadata, validate_training_run)

# ketos 7.0.2's default segmentation network, passed explicitly so the record is complete.
DEFAULT_SEG_SPEC = ("[1,1800,0,3 Cr7,7,64,2,2 Gn32 Cr3,3,128,2,2 Gn32 Cr3,3,128 Gn32 Cr3,3,256 Gn32 "
                    "Cr3,3,256 Gn32 Lbx32 Lby32 Cr1,1,32 Gn32 Lby32 Lbx32]")
# How `heocr-engine kraken` uses a segmenter: `kraken segment -bl -i MODEL` without `-d`, so kraken orders
# lines with its heuristic polygonal_reading_order and the horizontal-lr column hint. segtrain trains no
# reading-order head (that is `ketos rotrain`).
INFERENCE = {"command": "heocr-engine kraken", "segmenter": "kraken segment -bl", "text_direction": "horizontal-lr",
             "reading_order": "polygonal_reading_order", "neural_reading_order": False}
SEG_LOG_PATTERNS = {
    "parsed": re.compile(r"Parsing (\d+) XML files for (training|evaluation) data"),
    "failed": re.compile(r"Failed to parse "),
    "validation": re.compile(r"validation run: accuracy (\S+) mean_acc (\S+) mean_iu (\S+) freq_iu (\S+)"),
    "baselines": re.compile(r"validation bl detection: P (\S+) R (\S+) F1 (\S+)"),
    "stopping_threshold": re.compile(r"Stopping threshold reached"),
    "epoch_limit": re.compile(r"`max_epochs=\d+` reached"),
}


@dataclass(frozen=True)
class SegmentationHyperparameters:
    spec: str = DEFAULT_SEG_SPEC
    learning_rate: float = 0.0002
    optimizer: str = "AdamW"
    schedule: str = "constant"
    weight_decay: float = 0.00001
    quit: str = "early"
    epochs: int = -1
    min_epochs: int = 5
    lag: int = 10
    validation_frequency: float = 1.0
    line_width: int = 8
    baseline_tolerance: float = 10.0
    dice_weight: float = 0.5
    augment: bool = False

    def check(self) -> None:
        finite = all(math.isfinite(value) for value in (self.learning_rate, self.weight_decay,
                                                         self.validation_frequency, self.baseline_tolerance,
                                                         self.dice_weight))
        if (not isinstance(self.spec, str) or not self.spec.startswith("[") or len(self.spec) > 2000 or not finite
                or not 0 < self.learning_rate < 1 or not 0 <= self.weight_decay < 1
                or not _is_int(self.min_epochs, 0, 100_000) or not _is_int(self.lag, 1, 100_000)
                or not 0 < self.validation_frequency <= 100 or not _is_int(self.line_width, 1, 100)
                or not 0 < self.baseline_tolerance <= 1000 or not 0 <= self.dice_weight <= 1
                or self.optimizer not in OPTIMIZERS or self.schedule not in SCHEDULES
                or self.quit not in ("early", "fixed")
                or not (_is_int(self.epochs, 1, 100_000) or (self.quit == "early" and self.epochs == -1))):
            raise EngineError("Invalid segmentation training hyperparameters")

    def ketos_args(self) -> list[str]:
        # No -bl: under click 8.2 ketos 7.0.2 stores `-bl` as the string 'False', which kraken's segmenter
        # rejects at inference. The default is the same baseline location, stored as false.
        return ["-s", self.spec, "-r", repr(self.learning_rate), "--optimizer", self.optimizer,
                "--schedule", self.schedule, "-w", repr(self.weight_decay), "-q", self.quit,
                "-N", str(self.epochs), "--min-epochs", str(self.min_epochs), "--lag", str(self.lag),
                "-F", repr(self.validation_frequency), "--line-width", str(self.line_width),
                "--bl-tol", repr(self.baseline_tolerance), "--dice-weight", repr(self.dice_weight),
                "--augment" if self.augment else "--no-augment"]


def _float(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise EngineError("Invalid validation line in the ketos log") from exc
    if not math.isfinite(value):
        raise EngineError("Invalid validation line in the ketos log")
    return value


def _scan_segmentation_log(path: Path) -> dict:
    found: dict = {"stopped_by": None, "parsed_pages": {}, "parse_failures": 0, "history": []}
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            if (match := SEG_LOG_PATTERNS["parsed"].search(line)):
                found["parsed_pages"]["train" if match[2] == "training" else "validation"] = int(match[1])
            if SEG_LOG_PATTERNS["failed"].search(line):
                found["parse_failures"] += 1
            if (match := SEG_LOG_PATTERNS["validation"].search(line)):
                found["history"].append({"run": len(found["history"]), "val_accuracy": _float(match[1]),
                                         "val_mean_acc": _float(match[2]), "val_mean_iu": _float(match[3]),
                                         "val_freq_iu": _float(match[4]), "baseline_precision": None,
                                         "baseline_recall": None, "baseline_f1": None})
            if (match := SEG_LOG_PATTERNS["baselines"].search(line)) and found["history"]:
                found["history"][-1].update(baseline_precision=_float(match[1]), baseline_recall=_float(match[2]),
                                            baseline_f1=_float(match[3]))
            for outcome in ("stopping_threshold", "epoch_limit"):
                if SEG_LOG_PATTERNS[outcome].search(line):
                    found["stopped_by"] = outcome
    return found


def _segmentation_model(meta: dict, region_types: set[str]) -> dict:
    """Check the weights hold one baseline segmenter for exactly the trained classes; return its mapping."""
    models = [model for model in meta.values() if isinstance(model, dict)
              and "segmentation" in model.get("_tasks", ())]
    if len(models) != 1 or len(meta) != 1:
        raise EngineError("Expected exactly one segmentation model in the weights file")
    model = models[0]
    mapping = model.get("class_mapping")
    if not isinstance(mapping, dict) or not all(isinstance(mapping.get(key), dict) for key in ("baselines", "regions")):
        raise EngineError("Segmentation model has no class mapping")
    # kraken maps topline True/False/None to top/bottom/centre and fails on anything else.
    if model.get("topline") is not False:
        raise EngineError("Segmentation model does not record a baseline (bottom) line location")
    if set(mapping["baselines"]) != {"default"} or set(mapping["regions"]) != region_types:
        raise EngineError("Segmentation model classes do not match the training data")
    return mapping


def train_kraken_segmentation(annotations: Path, manifest: Path, work: Path, ketos: Path, *,
                              kraken: Path | None = None, corpora: tuple[Path, ...] = (), device: str = "cpu",
                              seed: int = 42, deterministic: bool = False, precision: str = "32-true",
                              workers: int = 0, threads: int = 1, validation_fraction: float = 0.1,
                              split_seed: int = 0,
                              hyperparameters: SegmentationHyperparameters = SegmentationHyperparameters(),
                              timeout: float = 172_800) -> dict:
    """Prepare typed-region PAGE XML, train a baseline segmenter from scratch with local ketos, describe the run."""
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
    summary = prepare_kraken_data(annotations, manifest, work / "data", validation_fraction, split_seed,
                                  task="segmentation")
    region_types = set(summary["train"]["regions_by_type"])
    if not set(summary["validation"]["regions_by_type"]) <= region_types:
        raise EngineError("The validation split has region types the train split lacks")
    commands = {"train": [str(ketos), "-v", "-d", device, "-s", str(seed),
                          "--deterministic" if deterministic else "--no-deterministic", "--precision", precision,
                          "--workers", str(workers), "--threads", str(threads), "segtrain", "-f", "page",
                          "-o", str(work / "checkpoints"), "--weights-format", "safetensors",
                          *hyperparameters.ketos_args(), "-t", str(work / "data" / "train.txt"),
                          "-e", str(work / "data" / "validation.txt")]}
    # Operators without an MPS kernel fall back to the CPU instead of failing.
    environment = {"PYTORCH_ENABLE_MPS_FALLBACK": "1"} if device == "mps" else {}
    log = work / "ketos.log"
    with log.open("ab") as stream:
        stream.write(b"# heocr-engine: train\n")
        stream.flush()
        # A wide virtual terminal stops ketos's rich logger from wrapping the lines the scanner reads.
        run_process(commands["train"], timeout, name="ketos", log=stream, env={"COLUMNS": "1000", **environment})
    if log.stat().st_size > MAX_LOG_BYTES:
        raise EngineError("ketos log exceeds the size limit")
    best = [path for path in (work / "checkpoints").glob("best_*.safetensors") if BEST.fullmatch(path.name)]
    if len(best) != 1:
        raise EngineError("ketos did not write exactly one best model")
    model = read_limited(best[0], MAX_MODEL_BYTES)
    class_mapping = _segmentation_model(safetensors_kraken_metadata(best[0]), region_types)
    score_text = BEST.fullmatch(best[0].name)[1]
    # ketos keeps the 10 best checkpoints, named by epoch and val_mean_iu; the earliest at the best score.
    best_epochs = [int(match[1]) for path in (work / "checkpoints").glob("checkpoint_*.ckpt")
                   if (match := CHECKPOINT.fullmatch(path.name)) and match[2] == score_text]
    scanned = _scan_segmentation_log(log)
    history = scanned["history"]
    stopped_by = ("epoch_limit" if hyperparameters.quit == "fixed" else scanned["stopped_by"]
                  or _stop_from_history(history, hyperparameters, "val_mean_iu") or "unknown")
    tokens = {str(ketos): "<ketos>", str(work): "<work>"}
    record = {
        "schema_version": TRAINING_SCHEMA_ID,
        "engine": {"name": "heocr-engine", "version": __version__},
        "trainer": trainer,
        "task": "segmentation",
        "init": "from_scratch",
        "data": {**summary, "corpora": corpus_records},
        "segmentation": {"line_location": "baseline", "line_types": ["default"],
                         "region_types": sorted(region_types), "region_type_source": "hocrsyngen region name",
                         "region_geometry": summary["region_geometry"], "class_mapping": class_mapping,
                         "inference": INFERENCE},
        "commands": {name: _portable(args, tokens) for name, args in commands.items()},
        "hyperparameters": asdict(hyperparameters),
        "run": {"seed": seed, "deterministic": deterministic, "device": device, "precision": precision,
                "workers": workers, "threads": threads, "environment": environment},
        "outcome": {"quit": hyperparameters.quit, "stopped_by": stopped_by,
                    "best_epoch": min(best_epochs) if best_epochs else None,
                    "validation_runs": len(history),
                    "epochs_completed": len(history) if hyperparameters.validation_frequency == 1 else None,
                    "validation_metric": {"name": "val_mean_iu", "best": float(score_text),
                                          "definition": "ketos mean intersection over union of the region and "
                                                        "separator pixel classes on the validation split, "
                                                        "kraken-internal; not a line-level or hocrgen score"},
                    "validation_history": history,
                    "ketos_listed_pages": scanned["parsed_pages"] or None,
                    "ketos_parse_failures": scanned["parse_failures"]},
        "output": {"model_sha256": digest(model), "bytes": len(model), "file_name": best[0].name,
                   "weights_format": "safetensors", "byte_reproducible": False},
        "model_licence": {"status": LICENCE_STATUS, "owner": "maintainer",
                          "basis": "planning/decisions/0008-first-trained-segmenter.md",
                          "published": False},
    }
    problems = validate_training_run(record)
    if problems:
        raise EngineError("Invalid training run record: " + "; ".join(problems))
    return record
