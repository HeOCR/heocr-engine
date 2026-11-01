"""Kraken baseline: run an installed kraken CLI with local, hashed segmentation and recognition models.

No model is bundled or downloaded. See docs/baselines.md and planning/decisions/0006-model-licences.md.
"""
from __future__ import annotations

import math
from pathlib import Path
import re
import tempfile

from heocr_engine.cli import EngineError, digest, read_limited, run_process
from heocr_engine.stages import Page, RecognitionResult, StageInfo, config_digest

BASE_DIRS = ("L", "R", "auto")
MAX_MODEL_BYTES = 2_000_000_000
VERSION = re.compile(r"kraken, version ([A-Za-z0-9.+_~-]+)")


def kraken_recognize(raw: bytes, executable: Path, segmentation_model: Path,
                     recognition_model: Path, base_dir: str = "R",
                     timeout: float = 600) -> tuple[str, dict]:
    """Return raw text and engine provenance. Kraken reorders code points to logical order."""
    if base_dir not in BASE_DIRS:
        raise EngineError("Invalid base direction")
    if not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise EngineError("Invalid timeout")
    executable = executable.resolve()
    segmentation_model = segmentation_model.resolve()
    recognition_model = recognition_model.resolve()
    provenance = {"executable_sha256": digest(read_limited(executable, 200_000_000)),
                  "segmentation_model_sha256": digest(read_limited(segmentation_model, MAX_MODEL_BYTES)),
                  "recognition_model_sha256": digest(read_limited(recognition_model, MAX_MODEL_BYTES))}
    try:
        match = VERSION.fullmatch(run_process([str(executable), "--version"], timeout)
                                  .decode("utf-8").strip())
    except UnicodeDecodeError as exc:
        raise EngineError("Invalid kraken version output") from exc
    if not match:
        raise EngineError("Invalid kraken version output")
    with tempfile.TemporaryDirectory(prefix="heocr-") as temp:
        root = Path(temp)
        source = root / ("input.png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else "input.jpg")
        source.write_bytes(raw)
        target = root / "result.txt"
        # Baseline segmentation, then recognition with reordering to Unicode logical order.
        run_process([str(executable), "-i", str(source), str(target),
                     "segment", "-bl", "-i", str(segmentation_model),
                     "ocr", "-m", str(recognition_model), "--reorder", "--base-dir", base_dir],
                    timeout)
        try:
            text = read_limited(target, 50_000_000).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise EngineError("Invalid kraken output encoding") from exc
    return text, {"name": "kraken", "version": match.group(1), "base_dir": base_dir, **provenance}


class KrakenRecognizer:
    """Kraken as one recognize stage; its segmentation model is listed among the artifacts."""

    def __init__(self, executable: Path, segmentation_model: Path, recognition_model: Path,
                 base_dir: str = "R", timeout: float = 600):
        self.executable, self.timeout, self.base_dir = executable, timeout, base_dir
        self.segmentation_model, self.recognition_model = segmentation_model, recognition_model
        self.info = StageInfo("recognize", "kraken", "unknown", deterministic=True,
                              license="Apache-2.0",
                              config_sha256=config_digest({"base_dir": base_dir, "reorder": True}))

    def recognize(self, page: Page) -> RecognitionResult:
        text, engine = kraken_recognize(page.data, self.executable, self.segmentation_model,
                                        self.recognition_model, self.base_dir, self.timeout)
        artifacts = (("executable", engine["executable_sha256"]),
                     ("model:segmentation", engine["segmentation_model_sha256"]),
                     ("model:recognition", engine["recognition_model_sha256"]))
        self.info = StageInfo("recognize", "kraken", engine["version"], deterministic=True,
                              license="Apache-2.0", artifacts=artifacts,
                              config_sha256=self.info.config_sha256)
        # Kraken's plain-text output has no word geometry; words stay empty.
        return RecognitionResult(text, [], {"base_dir": self.base_dir, "reorder": True})
