"""Composable open-track stages: preprocess* -> recognize -> postcorrect* (docs/stages.md)."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
from importlib import metadata
import json
from pathlib import Path
import shutil
from typing import Protocol, runtime_checkable

from heocr_engine import __version__
from heocr_engine.cli import (EngineError, MAX_BYTES, digest, inspect_image, read_limited,
                              run_process, tesseract_recognize)
from heocr_engine.contract import SCHEMA_ID
from heocr_engine.validate import _validate_stage, _validate_word, validate_prediction

STAGE_PROTOCOL = "heocr_engine_stage.v1"
ENTRY_POINT_GROUP = "heocr_engine.stages"
MAX_RESPONSE_BYTES = 100_000_000


@dataclass(frozen=True)
class Page:
    """Image bytes handed between stages. `width`/`height` are the input frame for all geometry."""
    data: bytes
    width: int
    height: int

    @property
    def media_type(self) -> str:
        return "image/png" if self.data.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg"


@dataclass(frozen=True)
class RecognitionResult:
    text: str
    words: list[dict] = field(default_factory=list)
    details: dict | None = None


@dataclass(frozen=True)
class StageInfo:
    kind: str
    name: str
    version: str
    deterministic: bool
    requires_network: bool = False
    track: str = "open"
    license: str | None = None
    artifacts: tuple[tuple[str, str], ...] = ()
    config_sha256: str | None = None

    def record(self, details: dict | None = None) -> dict:
        record = {"kind": self.kind, "name": self.name, "version": self.version,
                  "track": self.track, "deterministic": self.deterministic,
                  "requires_network": self.requires_network, "license": self.license,
                  "artifacts": [{"role": role, "sha256": sha} for role, sha in self.artifacts]}
        if self.config_sha256:
            record["config_sha256"] = self.config_sha256
        if details:
            record["details"] = details
        return record


@runtime_checkable
class Preprocessor(Protocol):
    info: StageInfo

    def process(self, page: Page) -> Page: ...


@runtime_checkable
class Recognizer(Protocol):
    info: StageInfo

    def recognize(self, page: Page) -> RecognitionResult: ...


@runtime_checkable
class PostCorrector(Protocol):
    info: StageInfo

    def correct(self, page: Page, result: RecognitionResult) -> RecognitionResult: ...


def config_digest(config) -> str:
    canonical = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                           allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_stage(stage, kind: str) -> None:
    info = getattr(stage, "info", None)
    if not isinstance(info, StageInfo) or info.kind != kind:
        raise EngineError(f"Expected a {kind} stage")
    # The runner executes open-track, network-free stages only (planning decision 0005).
    if info.track != "open" or info.requires_network:
        raise EngineError(f"Stage {info.name} is not open-track and network-free; submit its "
                          "predictions with validate-predictions instead")
    errors = _validate_stage(info.record(), 0)
    if errors:
        raise EngineError(f"Invalid stage metadata for {info.name}: {errors[0]}")


def _check_result(result, page: Page, name: str) -> RecognitionResult:
    if not isinstance(result, RecognitionResult) or not isinstance(result.text, str) \
            or not isinstance(result.words, list):
        raise EngineError(f"Stage {name} returned an invalid result")
    for index, word in enumerate(result.words):
        if _validate_word(word, index, page.width, page.height):
            raise EngineError(f"Stage {name} returned invalid word data")
    if result.details is not None and not isinstance(result.details, dict):
        raise EngineError(f"Stage {name} returned invalid details")
    return result


def run_pipeline(raw: bytes, recognizer, preprocessors=(), postcorrectors=()) -> dict:
    """Run stages on one image and return a heocr_engine_prediction.v1 record."""
    width, height = inspect_image(raw)
    for stage in preprocessors:
        _check_stage(stage, "preprocess")
    _check_stage(recognizer, "recognize")
    for stage in postcorrectors:
        _check_stage(stage, "postcorrect")
    page = Page(raw, width, height)
    pipeline = []
    for stage in preprocessors:
        processed = stage.process(page)
        if not isinstance(processed, Page) or not isinstance(processed.data, bytes):
            raise EngineError(f"Stage {stage.info.name} returned an invalid page")
        if len(processed.data) > MAX_BYTES or inspect_image(processed.data) != (width, height):
            # Word boxes are reported in the input frame; geometric transforms need a mapping first.
            raise EngineError(f"Stage {stage.info.name} changed the image size, which is unsupported")
        page = processed
        pipeline.append(stage.info.record())
    result = _check_result(recognizer.recognize(page), page, recognizer.info.name)
    pipeline.append(recognizer.info.record(result.details))
    for stage in postcorrectors:
        result = _check_result(stage.correct(page, result), page, stage.info.name)
        pipeline.append(stage.info.record(result.details))
    sha = digest(raw)
    prediction = {"schema_version": SCHEMA_ID, "page_id": "sha256:" + sha,
                  "input": {"sha256": sha, "width": width, "height": height}, "track": "open",
                  "engine": {"name": "heocr-engine-pipeline", "version": __version__},
                  "text": result.text, "words": result.words, "pipeline": pipeline}
    errors, _ = validate_prediction(prediction)
    if errors:
        raise EngineError(f"Pipeline produced an invalid prediction: {errors[0]}")
    return prediction


class TesseractRecognizer:
    """The PR #1 Tesseract baseline as a recognize stage."""

    def __init__(self, executable: Path, tessdata: Path, language: str = "heb", psm: int = 3,
                 timeout: float = 60):
        self.executable, self.tessdata = executable, tessdata
        self.language, self.psm, self.timeout = language, psm, timeout
        self.info = StageInfo("recognize", "tesseract", "unknown", deterministic=True,
                              license="Apache-2.0",
                              config_sha256=config_digest({"language": language, "psm": psm}))

    def recognize(self, page: Page) -> RecognitionResult:
        text, words, engine = tesseract_recognize(page.data, page.width, page.height,
                                                  self.executable, self.tessdata,
                                                  self.language, self.psm, self.timeout)
        artifacts = [("executable", engine["executable_sha256"])]
        artifacts += [(f"model:{model['language']}", model["sha256"]) for model in engine["models"]]
        self.info = StageInfo("recognize", "tesseract", engine["version"], deterministic=True,
                              license="Apache-2.0", artifacts=tuple(artifacts),
                              config_sha256=self.info.config_sha256)
        return RecognitionResult(text, words, {"psm": engine["psm"]})


class SubprocessStage:
    """Run a trusted local command that speaks heocr_engine_stage.v1 JSON on stdin/stdout.

    `requires_network` and `track` are declared by the stage manifest; the runner cannot
    enforce them, so only run commands you trust.
    """

    def __init__(self, manifest: dict, command: list[str], config: dict | None = None,
                 artifacts: dict[str, Path] | None = None, timeout: float = 60):
        if not command or not all(isinstance(part, str) and part for part in command):
            raise EngineError("Subprocess command must be a non-empty list of strings")
        resolved = shutil.which(command[0]) if "/" not in command[0] else command[0]
        if not resolved:
            raise EngineError("Subprocess executable not found")
        self.command = [str(Path(resolved).resolve()), *command[1:]]
        self.config = config or {}
        self.timeout = timeout
        hashed = [("executable", digest(read_limited(Path(self.command[0]), 200_000_000)))]
        for role, path in sorted((artifacts or {}).items()):
            hashed.append((role, digest(read_limited(Path(path), 2_000_000_000))))
        try:
            self.info = StageInfo(kind=manifest["kind"], name=manifest["name"],
                                  version=manifest["version"],
                                  deterministic=manifest["deterministic"],
                                  requires_network=manifest.get("requires_network", True),
                                  track=manifest.get("track", "open"),
                                  license=manifest.get("license"), artifacts=tuple(hashed),
                                  config_sha256=config_digest(self.config))
        except (KeyError, TypeError) as exc:
            raise EngineError("Stage manifest is missing required fields") from exc

    def _call(self, page: Page, **extra) -> dict:
        request = {"protocol": STAGE_PROTOCOL, "kind": self.info.kind, "config": self.config,
                   "page": {"media_type": page.media_type, "width": page.width, "height": page.height,
                            "image_base64": base64.b64encode(page.data).decode("ascii")}, **extra}
        stdout = run_process(self.command, self.timeout,
                             stdin=json.dumps(request, ensure_ascii=False).encode("utf-8"))
        if len(stdout) > MAX_RESPONSE_BYTES:
            raise EngineError(f"Stage {self.info.name} response exceeds the size limit")
        try:
            response = json.loads(stdout.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise EngineError(f"Stage {self.info.name} returned invalid JSON") from exc
        if not isinstance(response, dict):
            raise EngineError(f"Stage {self.info.name} returned invalid JSON")
        return response

    def _result(self, response: dict) -> RecognitionResult:
        details = response.get("details")
        return RecognitionResult(response.get("text"), response.get("words", []), details)

    def process(self, page: Page) -> Page:
        response = self._call(page)
        try:
            data = base64.b64decode(response["image_base64"], validate=True)
        except (KeyError, TypeError, ValueError) as exc:
            raise EngineError(f"Stage {self.info.name} returned no valid image") from exc
        width, height = inspect_image(data)
        return Page(data, width, height)

    def recognize(self, page: Page) -> RecognitionResult:
        return self._result(self._call(page))

    def correct(self, page: Page, result: RecognitionResult) -> RecognitionResult:
        return self._result(self._call(page, text=result.text, words=result.words))


def load_entry_point(name: str, config: dict):
    matches = [entry for entry in metadata.entry_points(group=ENTRY_POINT_GROUP) if entry.name == name]
    if len(matches) != 1:
        raise EngineError(f"Stage entry point {name!r} is not installed exactly once")
    stage = matches[0].load()(config)
    return stage


def build_stage(spec: dict, base: Path):
    """Build one stage from a pipeline config entry; relative paths resolve against `base`."""
    def local(value) -> Path:
        path = Path(value)
        return path if path.is_absolute() else base / path

    kind = spec.get("type")
    if kind == "tesseract":
        return TesseractRecognizer(local(spec["executable"]), local(spec["tessdata_dir"]),
                                   spec.get("language", "heb"), spec.get("psm", 3),
                                   spec.get("timeout", 60))
    if kind == "subprocess":
        manifest = json.loads(read_limited(local(spec["manifest"]), 1_000_000).decode("utf-8"))
        command = list(spec["command"])
        if command and ("/" in command[0]):
            command[0] = str(local(command[0]))
        artifacts = {role: local(path) for role, path in spec.get("artifacts", {}).items()}
        return SubprocessStage(manifest, command, spec.get("config"), artifacts,
                               spec.get("timeout", 60))
    if kind == "entry_point":
        return load_entry_point(spec["name"], spec.get("config", {}))
    raise EngineError(f"Unknown stage type {kind!r}")


def run_config(image: Path, config_path: Path) -> dict:
    """Run the pipeline described by a JSON config file on one image."""
    try:
        config = json.loads(read_limited(config_path, 1_000_000).decode("utf-8"))
        specs = config["stages"]
        base = config_path.resolve().parent
        stages = [build_stage(spec, base) for spec in specs]
    except (KeyError, TypeError, ValueError, UnicodeDecodeError) as exc:
        raise EngineError("Invalid pipeline config") from exc
    kinds = [stage.info.kind for stage in stages]
    if kinds.count("recognize") != 1:
        raise EngineError("A pipeline needs exactly one recognize stage")
    split = kinds.index("recognize")
    if any(kind != "preprocess" for kind in kinds[:split]) \
            or any(kind != "postcorrect" for kind in kinds[split + 1:]):
        raise EngineError("Stages must be ordered preprocess*, recognize, postcorrect*")
    return run_pipeline(read_limited(image, MAX_BYTES), stages[split], stages[:split],
                        stages[split + 1:])
