"""Kraken through its Python API, with an optional learned line reading order (R4d2, opt-in).

The CLI stage in heocr_engine.kraken stays the default. This stage runs kraken in-process (the `kraken`
extra) so that it can apply a `ketos rotrain` reading-order model and emit the text in that order, and so
that it can hand image-bound line geometry and the predicted typed regions to later stages.

Kraken 7.0.2 computes no usable learned order for us: `kraken ... ocr` writes plain text in the
heuristic order even when a reading-order model is attached, and the deprecated `blla.segment` stores
the learned order as indices into its pre-sort line list next to the heuristically re-sorted lines
(tests/test_kraken_api.py proves it). So the order is recomputed here from the pre-sort list and mapped
onto the returned lines by line id. No model is bundled or downloaded.

By default the reading-order model sees the segmenter's line types (its `baselines` class mapping). With
`reading_order_classes="region"` (R4e, opt-in) each line is instead tagged with a predicted region type and the
reading-order model's own class mapping is used: Kraken's line features carry only position and line type, so a
line-typed model cannot learn layouts such as a label column beside body text.
"""
from __future__ import annotations

from collections import Counter
import copy
from importlib import metadata
import io
import math
from pathlib import Path

from heocr_engine.cli import EngineError, digest, read_limited
from heocr_engine.kraken import BASE_DIRS, DIRECTION_FOR_BASE, MAX_MODEL_BYTES, TEXT_DIRECTIONS
from heocr_engine.stages import Page, RecognitionResult, StageInfo, config_digest

GEOMETRY_SCHEMA = "heocr_engine_kraken_geometry.v1"
DEVICES = ("cpu", "mps", "cuda")
READING_ORDER_CLASSES = ("segmenter", "region")
# Region mode: a line the segmenter typed `stamp` (trained with --line-type stamp_area=stamp) is a stamp_area
# line even though it also lies in the body region under it.
STAMP_LINE_TYPE, STAMP_REGION = "stamp", "stamp_area"


def _kraken():
    """Import the kraken pieces this stage uses; tests replace this function."""
    try:
        from PIL import Image
        from kraken.configs import RecognitionInferenceConfig, SegmentationInferenceConfig
        from kraken.ketos.util import to_ptl_device
        from kraken.lib.segmentation import neural_reading_order, polygonal_reading_order
        from kraken.models import load_models
        from kraken.tasks import RecognitionTaskModel, SegmentationTaskModel
    except ImportError as exc:
        raise EngineError("The Python kraken stage needs kraken installed (pip install "
                          "'heocr-engine[kraken]')") from exc
    return {"Image": Image, "RecognitionInferenceConfig": RecognitionInferenceConfig,
            "SegmentationInferenceConfig": SegmentationInferenceConfig,
            "neural_reading_order": neural_reading_order,
            "polygonal_reading_order": polygonal_reading_order, "load_models": load_models,
            "RecognitionTaskModel": RecognitionTaskModel, "SegmentationTaskModel": SegmentationTaskModel,
            "to_ptl_device": to_ptl_device,
            "version": metadata.version("kraken"),
            "record_sha256": digest((metadata.distribution("kraken").read_text("RECORD") or "").encode())}


class _PreSortRecorder:
    """Wrap kraken's heuristic line order to keep the list it was given (the pre-sort list)."""

    def __init__(self, function):
        self.function, self.pre_sort = function, None

    def __call__(self, lines, regions=None, text_direction="lr"):
        self.pre_sort = list(lines)
        return self.function(lines=lines, regions=regions, text_direction=text_direction)


def learned_line_order(pre_sort, returned, order) -> list[int]:
    """Map a learned order over `pre_sort` (indices into it) to indices into `returned`.

    Both lists hold the same lines, matched by line id. Fails closed unless the result is a permutation.
    """
    positions = {line.id: index for index, line in enumerate(returned)}
    if len(positions) != len(returned) or len(pre_sort) != len(returned) \
            or {line.id for line in pre_sort} != set(positions):
        raise EngineError("Kraken returned lines that do not match its pre-sort list")
    try:
        mapped = [positions[pre_sort[int(index)].id] for index in order]
    except (IndexError, TypeError, ValueError) as exc:
        raise EngineError("The reading-order model returned an invalid order") from exc
    if sorted(mapped) != list(range(len(returned))):
        raise EngineError("The reading-order model returned an invalid order")
    return mapped


def _type(tags) -> str:
    """Kraken's tag layout is {"type": [{"type": name}]}; older files use {"type": name}."""
    value = (tags or {}).get("type", "default")
    if isinstance(value, list) and value and isinstance(value[0], dict):
        value = value[0].get("type", "default")
    return value if isinstance(value, str) and value else "default"


def region_line_classes(lines, regions) -> list[str]:
    """Reading-order class of each line in region mode: `stamp_area` for a line typed `stamp`, else the type of
    the first region Kraken lists for it, else "default"."""
    region_type = {region.id: kind for kind, items in (regions or {}).items() for region in items}
    classes = []
    for line in lines:
        listed = [region_type[r] for r in line.regions or [] if r in region_type]
        classes.append(STAMP_REGION if _type(line.tags) == STAMP_LINE_TYPE else listed[0] if listed else "default")
    return classes


def _tagged(lines, classes):
    """Copies of the lines carrying the reading-order classes as their type; kraken's own lines stay unchanged."""
    tagged = []
    for line, name in zip(lines, classes):
        line = copy.copy(line)
        line.tags = {"type": [{"type": name}]}
        tagged.append(line)
    return tagged


def _points(points, width: int, height: int) -> tuple[list[list[float]], bool]:
    """Clamp a polyline or polygon to the image; report whether any point moved."""
    clamped, moved = [], False
    for x, y in points or []:
        x, y = float(x), float(y)
        if not (math.isfinite(x) and math.isfinite(y)):
            raise EngineError("Kraken returned non-finite geometry")
        cx, cy = min(max(x, 0.0), float(width)), min(max(y, 0.0), float(height))
        moved = moved or (cx, cy) != (x, y)
        clamped.append([round(cx, 2), round(cy, 2)])
    return clamped, moved


def _bbox(points) -> list[float] | None:
    if not points:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return [min(xs), min(ys), round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2)]


def page_geometry(segmentation, records, emitted, input_sha256: str, width: int, height: int,
                  line_order: str) -> dict:
    """Image-bound lines (in emitted order) and predicted typed regions, e.g. `table_cells`.

    Predicted regions are this segmenter's own detections, not generator gold. Ids are page-local.
    """
    region_ids, regions = {}, []
    for region_type in sorted(segmentation.regions or {}):
        for region in segmentation.regions[region_type]:
            boundary, clipped = _points(region.boundary, width, height)
            region_ids[region.id] = f"r{len(regions)}"
            regions.append({"id": region_ids[region.id], "type": region_type, "boundary": boundary,
                            "bbox": _bbox(boundary), "clipped": clipped})
    by_id = {record.id: record for record in records}
    lines = []
    for position, index in enumerate(emitted):
        line = segmentation.lines[index]
        baseline, clipped_baseline = _points(line.baseline, width, height)
        boundary, clipped_boundary = _points(line.boundary, width, height)
        record = by_id[line.id]
        lines.append({"id": f"l{index}", "order": position, "heuristic_order": index,
                      "type": _type(line.tags), "regions": [region_ids[r] for r in line.regions or []
                                                            if r in region_ids],
                      "baseline": baseline, "boundary": boundary, "bbox": _bbox(boundary),
                      "clipped": clipped_baseline or clipped_boundary,
                      "text": record.prediction})
    return {"schema_version": GEOMETRY_SCHEMA, "input_sha256": input_sha256, "unit": "pixel",
            "width": width, "height": height, "text_direction": segmentation.text_direction,
            "line_order": line_order, "lines": lines, "regions": regions}


class KrakenPythonRecognizer:
    """Kraken segmentation and recognition in-process; optional learned line order from a separate model.

    The reading-order model is loaded from its own file so that its hash is recorded on its own; any
    reading-order model embedded in the segmentation file is ignored. `reading_order_classes` picks what it
    sees as each line's class: the segmenter's line types (default) or predicted region types ("region").
    """

    def __init__(self, segmentation_model: Path, recognition_model: Path,
                 reading_order_model: Path | None = None, base_dir: str = "R",
                 text_direction: str | None = None, device: str = "cpu",
                 reading_order_classes: str = "segmenter"):
        if base_dir not in BASE_DIRS:
            raise EngineError("Invalid base direction")
        self.text_direction = text_direction or DIRECTION_FOR_BASE.get(base_dir) or "horizontal-lr"
        if self.text_direction not in TEXT_DIRECTIONS:
            raise EngineError("Invalid text direction")
        if device not in DEVICES:
            raise EngineError("Invalid device")
        if reading_order_classes not in READING_ORDER_CLASSES:
            raise EngineError("Invalid reading-order classes")
        if reading_order_classes == "region" and reading_order_model is None:
            raise EngineError("Region reading-order classes need a reading-order model")
        self.base_dir, self.device, self.reading_order_classes = base_dir, device, reading_order_classes
        self.paths = {"model:segmentation": segmentation_model.resolve(),
                      "model:recognition": recognition_model.resolve()}
        if reading_order_model is not None:
            self.paths["model:reading-order"] = reading_order_model.resolve()
        self.hashes = {role: digest(read_limited(path, MAX_MODEL_BYTES)) for role, path in self.paths.items()}
        self.last_geometry = None
        self._models = None
        self.info = StageInfo("recognize", "kraken-python", "unknown", deterministic=True,
                              license="Apache-2.0", config_sha256=config_digest(self._config()))

    def _config(self) -> dict:
        config = {"api": "python", "base_dir": self.base_dir, "reorder": True,
                  "text_direction": self.text_direction,
                  "neural_reading_order": "model:reading-order" in self.paths}
        if self.reading_order_classes != "segmenter":  # the default keeps its earlier config digest
            config["reading_order_classes"] = self.reading_order_classes
        return config

    def _load(self, k):
        if self._models is None:
            def only(path, task):
                models = [m for m in k["load_models"](path, tasks=[task]) if task in m.model_type]
                if len(models) != 1:
                    raise EngineError(f"Expected exactly one {task} model in {path.name}")
                return models[0]

            segmentation = only(self.paths["model:segmentation"], "segmentation")
            recognition = only(self.paths["model:recognition"], "recognition")
            reading_order = None
            if "model:reading-order" in self.paths:
                reading_order = only(self.paths["model:reading-order"], "reading_order")
                if reading_order.user_metadata.get("level", "baselines") != "baselines":
                    raise EngineError("Only line-level (baselines) reading-order models are supported")
                seg_mapping = segmentation.user_metadata.get("class_mapping", {})
                ro_classes = set(reading_order.user_metadata.get("class_mapping", {})) - {"default"}
                line_types = set(seg_mapping.get("baselines", {})) - {"default"}
                if self.reading_order_classes == "segmenter":
                    if ro_classes != line_types:
                        raise EngineError("Reading-order and segmentation models know different line types")
                else:
                    self._check_region_classes(reading_order.user_metadata.get("class_mapping", {}),
                                               set(seg_mapping.get("regions", {})), line_types)
            self._models = (k["SegmentationTaskModel"]([segmentation]),
                            k["RecognitionTaskModel"]([recognition]), segmentation, reading_order)
        return self._models

    @staticmethod
    def _check_region_classes(mapping, region_types: set, line_types: set) -> None:
        """Region mode: the reading-order classes must be region types this segmenter predicts."""
        if not isinstance(mapping, dict) or not all(
                isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in mapping.values()):
            raise EngineError("The reading-order model has an invalid class mapping")
        classes = set(mapping) - {"default"}
        if not classes or classes & line_types:
            raise EngineError("Region reading-order classes need a model trained on region types, "
                              "not on line types")
        if classes - region_types:
            raise EngineError("The reading-order model has region classes the segmenter never predicts: "
                              + ", ".join(sorted(classes - region_types)))
        if STAMP_LINE_TYPE in line_types and STAMP_REGION not in classes:
            raise EngineError(f"The segmenter types `{STAMP_LINE_TYPE}` lines, but the reading-order model has "
                              f"no `{STAMP_REGION}` class")

    def recognize(self, page: Page) -> RecognitionResult:
        k = _kraken()
        segmenter, recognizer, segmentation_net, reading_order = self._load(k)
        image = k["Image"].open(io.BytesIO(page.data))
        image.load()
        recorder = _PreSortRecorder(k["polygonal_reading_order"])
        accelerator, device = k["to_ptl_device"](self.device)  # as `kraken -d`
        config = k["SegmentationInferenceConfig"](text_direction=self.text_direction, accelerator=accelerator,
                                                  device=device, baseline_ro_fn=recorder)
        segmentation = segmenter.predict(im=image, config=config)
        lines = list(segmentation.lines or [])
        emitted = list(range(len(lines)))
        if reading_order is not None and len(lines) > 1:
            if recorder.pre_sort is None:
                raise EngineError("Kraken did not report its pre-sort line list")
            if self.reading_order_classes == "region":
                classes = region_line_classes(recorder.pre_sort, segmentation.regions)
                ro_lines, mapping = _tagged(recorder.pre_sort, classes), reading_order.user_metadata["class_mapping"]
            else:
                ro_lines = recorder.pre_sort
                mapping = segmentation_net.user_metadata["class_mapping"].get("baselines", {})
            order = k["neural_reading_order"](lines=ro_lines, model=reading_order, im_size=image.size,
                                              class_mapping=mapping)
            emitted = learned_line_order(recorder.pre_sort, lines, list(order))
        bidi = self.base_dir if self.base_dir != "auto" else True
        records = list(recognizer.predict(im=image, segmentation=segmentation,
                                          config=k["RecognitionInferenceConfig"](
                                              bidi_reordering=bidi, accelerator=accelerator,
                                              device=device, num_line_workers=0)))
        by_id = {record.id: record for record in records}
        # One record per segmented line, or the text and geometry would silently drop lines.
        if len(records) != len(lines) or set(by_id) != {line.id for line in lines}:
            raise EngineError("Kraken did not return exactly one recognition record per line")
        text = "\n".join(by_id[lines[i].id].prediction for i in emitted)
        line_order = "learned" if reading_order is not None else "heuristic"
        self.last_geometry = page_geometry(segmentation, records, emitted, digest(page.data),
                                           page.width, page.height, line_order)
        artifacts = (("library:kraken-record", k["record_sha256"]),
                     *((role, self.hashes[role]) for role in self.paths))
        self.info = StageInfo("recognize", "kraken-python", k["version"], deterministic=True,
                              license="Apache-2.0", artifacts=artifacts,
                              config_sha256=self.info.config_sha256)
        details = {**self._config(), "line_order": line_order, "lines": len(lines),
                   "lines_moved_by_learned_order": sum(1 for p, i in enumerate(emitted) if p != i),
                   "region_counts": {t: len(r) for t, r in sorted((segmentation.regions or {}).items())}}
        if reading_order is not None:
            details["reading_order_model_sha256"] = self.hashes["model:reading-order"]
        if self.reading_order_classes == "region":
            details["reading_order_class_counts"] = dict(sorted(Counter(
                region_line_classes(lines, segmentation.regions)).items()))
        # Kraken's line records carry no word geometry here; words stay empty, as in the CLI stage.
        return RecognitionResult(text, [], details)
