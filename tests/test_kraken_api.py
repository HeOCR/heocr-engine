import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import warnings

from PIL import Image

from heocr_engine.cli import EngineError, main
from heocr_engine import kraken_api
from heocr_engine.kraken_api import KrakenPythonRecognizer, learned_line_order, region_line_classes
from heocr_engine.stages import run_pipeline
from heocr_engine.validate import validate_prediction


class Line:
    def __init__(self, id, baseline, boundary, line_type="default", regions=()):
        self.id, self.baseline, self.boundary = id, baseline, boundary
        self.tags, self.regions = {"type": [{"type": line_type}]}, list(regions)


class Record:
    def __init__(self, id, prediction):
        self.id, self.prediction = id, prediction


class Region:
    def __init__(self, id, boundary):
        self.id, self.boundary = id, boundary


class Segmentation:
    def __init__(self, lines, regions, text_direction):
        self.lines, self.regions, self.text_direction = lines, regions, text_direction


class Net:
    def __init__(self, model_type, user_metadata=None):
        self.model_type, self.user_metadata = [model_type], user_metadata or {}


class Config:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


# Pre-sort list A, B, C: the heuristic reads C, A, B; the learned model reads A, B, C.
PRE_SORT = [Line("_a", [[10, 5], [30, 5]], [[10, 2], [30, 2], [30, 8], [10, 8]]),
            Line("_b", [[10, 12], [30, 12]], [[10, 9], [30, 9], [30, 15], [10, 15]], "stamp", ["_t"]),
            Line("_c", [[2, 18], [45, 18]], [[-3, 16], [45, 16], [45, 21], [-3, 21]])]
TEXT = {"_a": "שלום", "_b": "Hello", "_c": "עולם"}
CLASSES = {"baselines": {"default": 2, "stamp": 3}, "regions": {"table_cells": 4}}


class FakeKraken:
    def __init__(self, learned=(0, 1, 2)):
        self.learned, self.calls = list(learned), []

    def load_models(self, path, tasks):
        kind = {"seg.safetensors": "segmentation", "rec.safetensors": "recognition",
                "ro.safetensors": "reading_order"}[path.name]
        metadata = {"class_mapping": CLASSES} if kind == "segmentation" else {}
        if kind == "reading_order":
            metadata = {"level": "baselines", "class_mapping": {"default": 2, "stamp": 3}}
        return [Net(kind, metadata)]

    def segmenter(self, models):
        fake = self

        class Task:
            def predict(self, im, config):
                fake.calls.append(("segment", config.__dict__))
                order = config.baseline_ro_fn(lines=PRE_SORT, regions=[], text_direction="rl")
                return Segmentation([PRE_SORT[i] for i in order],
                                    {"table_cells": [Region("_t", [[5, 8], [60, 8], [60, 30], [5, 30]])]},
                                    config.text_direction)
        return Task()

    def recognizer(self, models):
        fake = self

        class Task:
            def predict(self, im, segmentation, config):
                fake.calls.append(("recognize", config.__dict__))
                return (Record(line.id, TEXT[line.id]) for line in segmentation.lines)
        return Task()

    def neural(self, lines, model, im_size, class_mapping):
        self.calls.append(("neural", [line.id for line in lines], im_size, class_mapping))
        return self.learned

    def modules(self):
        return {"Image": Image, "RecognitionInferenceConfig": Config, "SegmentationInferenceConfig": Config,
                "neural_reading_order": self.neural,
                "polygonal_reading_order": lambda lines, regions, text_direction: [2, 0, 1],
                "load_models": self.load_models, "RecognitionTaskModel": self.recognizer,
                "SegmentationTaskModel": self.segmenter, "to_ptl_device": lambda d: (d, "auto"),
                "version": "7.0.2", "record_sha256": "f" * 64}


class LearnedOrderTests(unittest.TestCase):
    def test_maps_pre_sort_indices_onto_returned_lines(self):
        returned = [PRE_SORT[i] for i in (2, 0, 1)]
        order = learned_line_order(PRE_SORT, returned, [0, 1, 2])
        self.assertEqual([returned[i].id for i in order], ["_a", "_b", "_c"])

    def test_fails_closed(self):
        returned = [PRE_SORT[i] for i in (2, 0, 1)]
        for order in ([0, 1], [0, 0, 1], [0, 1, 3]):
            with self.assertRaises(EngineError):
                learned_line_order(PRE_SORT, returned, order)
        with self.assertRaises(EngineError):
            learned_line_order(PRE_SORT, returned[:2], [0, 1])


class KrakenPythonStageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / "page.png"
        # Original synthetic image, with no source data.
        Image.new("RGB", (40, 20), "white").save(self.image)
        for name in ("seg", "rec", "ro"):
            (self.root / f"{name}.safetensors").write_bytes(name.encode())

    def stage(self, reading_order=True, **kwargs):
        return KrakenPythonRecognizer(self.root / "seg.safetensors", self.root / "rec.safetensors",
                                      self.root / "ro.safetensors" if reading_order else None, **kwargs)

    def run_stage(self, stage, fake):
        with patch.object(kraken_api, "_kraken", fake.modules):
            return run_pipeline(self.image.read_bytes(), stage)

    def test_learned_order_drives_the_text(self):
        fake, stage = FakeKraken(), self.stage()
        prediction = self.run_stage(stage, fake)
        self.assertEqual(validate_prediction(prediction)[0], [])
        self.assertEqual(prediction["text"], "שלום\nHello\nעולם")
        # The learned order is computed from the pre-sort list, not from the heuristically sorted lines.
        self.assertEqual(fake.calls[1][1], ["_a", "_b", "_c"])
        self.assertEqual(fake.calls[1][3], CLASSES["baselines"])
        record = prediction["pipeline"][0]
        self.assertEqual(record["name"], "kraken-python")
        self.assertEqual(record["version"], "7.0.2")
        self.assertEqual([a["role"] for a in record["artifacts"]],
                         ["library:kraken-record", "model:segmentation", "model:recognition",
                          "model:reading-order"])
        details = record["details"]
        self.assertTrue(details["neural_reading_order"])
        self.assertEqual(details["line_order"], "learned")
        self.assertEqual(details["reading_order_model_sha256"], record["artifacts"][3]["sha256"])
        self.assertEqual(details["lines_moved_by_learned_order"], 3)
        self.assertEqual(details["region_counts"], {"table_cells": 1})
        segment, recognize = fake.calls[0][1], fake.calls[2][1]
        self.assertEqual((segment["text_direction"], segment["accelerator"]), ("horizontal-rl", "cpu"))
        self.assertEqual((recognize["bidi_reordering"], recognize["num_line_workers"]), ("R", 0))

    def test_without_a_reading_order_model_keeps_the_heuristic_order(self):
        fake, stage = FakeKraken(), self.stage(reading_order=False)
        prediction = self.run_stage(stage, fake)
        self.assertEqual(prediction["text"], "עולם\nשלום\nHello")
        details = prediction["pipeline"][0]["details"]
        self.assertFalse(details["neural_reading_order"])
        self.assertEqual(details["line_order"], "heuristic")
        self.assertNotIn("reading_order_model_sha256", details)
        self.assertEqual([c[0] for c in fake.calls], ["segment", "recognize"])
        self.assertNotEqual(stage.info.config_sha256, self.stage().info.config_sha256)

    def test_geometry_is_image_bound_with_typed_regions(self):
        stage = self.stage()
        self.run_stage(stage, FakeKraken())
        geometry = stage.last_geometry
        self.assertEqual((geometry["schema_version"], geometry["unit"], geometry["width"], geometry["height"]),
                         ("heocr_engine_kraken_geometry.v1", "pixel", 40, 20))
        self.assertEqual(geometry["line_order"], "learned")
        self.assertEqual([(l["text"], l["order"], l["heuristic_order"]) for l in geometry["lines"]],
                         [("שלום", 0, 1), ("Hello", 1, 2), ("עולם", 2, 0)])
        stamp = geometry["lines"][1]
        self.assertEqual((stamp["type"], stamp["regions"]), ("stamp", ["r0"]))
        region = geometry["regions"][0]
        self.assertEqual((region["type"], region["bbox"], region["clipped"]),
                         ("table_cells", [5.0, 8.0, 35.0, 12.0], True))
        last = geometry["lines"][2]
        self.assertTrue(last["clipped"])
        self.assertEqual(last["bbox"], [0.0, 16.0, 40.0, 4.0])
        for item in geometry["lines"] + geometry["regions"]:
            for x, y in item["boundary"]:
                self.assertTrue(0 <= x <= 40 and 0 <= y <= 20)

    def test_invalid_learned_order_fails_closed(self):
        with self.assertRaises(EngineError):
            self.run_stage(self.stage(), FakeKraken(learned=(0, 0, 1)))

    def test_missing_or_extra_recognition_records_fail_closed(self):
        for records in (lambda lines: lines[:-1], lambda lines: lines + lines[:1]):
            fake = FakeKraken()

            def recognizer(models, records=records):
                class Task:
                    def predict(self, im, segmentation, config):
                        return iter([Record(line.id, TEXT[line.id]) for line in records(segmentation.lines)])
                return Task()

            fake.recognizer = recognizer
            for reading_order in (True, False):
                stage = self.stage(reading_order=reading_order)
                with self.assertRaises(EngineError):
                    self.run_stage(stage, fake)
                self.assertIsNone(stage.last_geometry)

    def test_rejects_region_level_and_mismatched_reading_order_models(self):
        for metadata in ({"level": "regions", "class_mapping": {}},
                         {"level": "baselines", "class_mapping": {"default": 2}}):
            fake = FakeKraken()
            load = fake.load_models
            fake.load_models = lambda path, tasks, load=load, metadata=metadata: (
                [Net("reading_order", metadata)] if path.name == "ro.safetensors" else load(path, tasks))
            with self.assertRaises(EngineError):
                self.run_stage(self.stage(), fake)

    def test_pipeline_config_builds_the_stage(self):
        from heocr_engine.stages import build_stage

        stage = build_stage({"type": "kraken-python", "segmentation_model": "seg.safetensors",
                             "recognition_model": "rec.safetensors", "reading_order_model": "ro.safetensors",
                             "device": "mps"}, self.root)
        self.assertIsInstance(stage, KrakenPythonRecognizer)
        self.assertEqual((stage.device, stage.text_direction), ("mps", "horizontal-rl"))
        self.assertIn("model:reading-order", stage.paths)

    def test_rejects_bad_settings(self):
        with self.assertRaises(EngineError):
            self.stage(device="tpu")
        with self.assertRaises(EngineError):
            self.stage(base_dir="X")


# Region mode: body lines _r1, _r3, a stamp _r2 that Kraken lists in the body region first, a label _r4 in
# table_cells and a line _r5 outside every region.
REGION_LINES = [Line("_r1", [[10, 5], [30, 5]], [[10, 2], [30, 2], [30, 8], [10, 8]], regions=["_body"]),
                Line("_r2", [[12, 7], [28, 7]], [[12, 4], [28, 4], [28, 10], [12, 10]], "stamp", ["_body", "_s"]),
                Line("_r3", [[10, 12], [30, 12]], [[10, 9], [30, 9], [30, 15], [10, 15]], regions=["_body"]),
                Line("_r4", [[32, 6], [38, 6]], [[32, 3], [38, 3], [38, 9], [32, 9]], regions=["_gone", "_t"]),
                Line("_r5", [[2, 18], [20, 18]], [[2, 16], [20, 16], [20, 19], [2, 19]])]
REGIONS = {"body": [Region("_body", [[8, 1], [31, 1], [31, 16], [8, 16]])],
           "stamp_area": [Region("_s", [[11, 3], [29, 3], [29, 11], [11, 11]])],
           "table_cells": [Region("_t", [[31, 2], [39, 2], [39, 10], [31, 10]])]}
REGION_SEG = {"baselines": {"default": 2, "stamp": 3},
              "regions": {"body": 4, "stamp_area": 5, "table_cells": 6, "footer": 7}}
REGION_RO = {"default": 0, "body": 2, "stamp_area": 3, "table_cells": 8}


class RegionFake(FakeKraken):
    def __init__(self, ro_mapping=REGION_RO, learned=(0, 1, 2, 3, 4)):
        super().__init__(learned)
        self.ro_mapping, self.tags_seen = ro_mapping, None

    def load_models(self, path, tasks):
        kind = {"seg.safetensors": "segmentation", "rec.safetensors": "recognition",
                "ro.safetensors": "reading_order"}[path.name]
        metadata = {"segmentation": {"class_mapping": REGION_SEG},
                    "reading_order": {"level": "baselines", "class_mapping": self.ro_mapping}}.get(kind, {})
        return [Net(kind, metadata)]

    def segmenter(self, models):
        class Task:
            def predict(self, im, config):
                order = config.baseline_ro_fn(lines=REGION_LINES, regions=[], text_direction="rl")
                return Segmentation([REGION_LINES[i] for i in order], REGIONS, config.text_direction)
        return Task()

    def recognizer(self, models):
        class Task:
            def predict(self, im, segmentation, config):
                return (Record(line.id, line.id) for line in segmentation.lines)
        return Task()

    def neural(self, lines, model, im_size, class_mapping):
        self.tags_seen = [line.tags["type"][0]["type"] for line in lines]
        self.calls.append(("neural", [line.id for line in lines], im_size, class_mapping))
        return self.learned

    def modules(self):
        return {**super().modules(),
                "polygonal_reading_order": lambda lines, regions, text_direction: [4, 3, 2, 1, 0]}


class RegionReadingOrderTests(unittest.TestCase):
    setUp, stage, run_stage = (KrakenPythonStageTests.setUp, KrakenPythonStageTests.stage,
                               KrakenPythonStageTests.run_stage)

    def test_region_classes_tag_lines_stamp_first_and_use_the_model_mapping(self):
        fake, stage = RegionFake(), self.stage(reading_order_classes="region")
        prediction = self.run_stage(stage, fake)
        # A `stamp` line is stamp_area even though Kraken lists the body region first; an unknown region id is
        # skipped; a line outside every region is "default".
        self.assertEqual(fake.tags_seen, ["body", "stamp_area", "body", "table_cells", "default"])
        self.assertEqual(fake.calls[-1][3], REGION_RO)
        self.assertEqual(prediction["text"], "_r1\n_r2\n_r3\n_r4\n_r5")
        # Kraken's own lines keep their types; only the reading-order copies are retagged.
        self.assertEqual([line.tags["type"][0]["type"] for line in REGION_LINES],
                         ["default", "stamp", "default", "default", "default"])
        self.assertEqual(stage.last_geometry["lines"][1]["type"], "stamp")
        details = prediction["pipeline"][0]["details"]
        self.assertEqual(details["reading_order_classes"], "region")
        self.assertEqual(details["reading_order_class_counts"],
                         {"body": 2, "default": 1, "stamp_area": 1, "table_cells": 1})
        self.assertEqual(details["line_order"], "learned")

    def test_default_classes_keep_the_earlier_config_digest(self):
        self.assertEqual(self.stage().info.config_sha256,
                         self.stage(reading_order_classes="segmenter").info.config_sha256)
        self.assertNotIn("reading_order_classes", self.stage()._config())
        self.assertNotEqual(self.stage().info.config_sha256,
                            self.stage(reading_order_classes="region").info.config_sha256)

    def test_region_classes_fail_closed(self):
        bad = ({"default": 2, "stamp": 3},              # a line-typed model
               {"default": 0},                           # no region classes
               {"default": 0, "body": 2, "stamp_area": 3, "margin": 9},  # the segmenter never predicts margin
               {"default": 0, "body": 2, "table_cells": 8},  # stamps would lose their class
               {"default": 0, "body": "2", "stamp_area": 3})  # not an index
        for mapping in bad:
            with self.subTest(mapping=mapping), self.assertRaises(EngineError):
                self.run_stage(self.stage(reading_order_classes="region"), RegionFake(ro_mapping=mapping))
        # The default mode still rejects a region-typed model against a line-typed segmenter.
        with self.assertRaises(EngineError):
            self.run_stage(self.stage(), RegionFake())
        with self.assertRaises(EngineError):
            self.stage(reading_order=False, reading_order_classes="region")
        with self.assertRaises(EngineError):
            self.stage(reading_order_classes="lines")

    def test_region_line_classes_rule(self):
        self.assertEqual(region_line_classes(REGION_LINES, REGIONS),
                         ["body", "stamp_area", "body", "table_cells", "default"])
        self.assertEqual(region_line_classes(REGION_LINES[:1], {}), ["default"])

    def test_pipeline_config_and_cli_pass_region_classes(self):
        from heocr_engine.stages import build_stage

        stage = build_stage({"type": "kraken-python", "segmentation_model": "seg.safetensors",
                             "recognition_model": "rec.safetensors", "reading_order_model": "ro.safetensors",
                             "reading_order_classes": "region"}, self.root)
        self.assertEqual(stage.reading_order_classes, "region")
        args = [str(self.image), str(self.root / "out.json"), "--segmentation-model",
                str(self.root / "seg.safetensors"), "--recognition-model", str(self.root / "rec.safetensors")]
        with patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit):
            main(["kraken", *args, "--executable", "kraken", "--reading-order-classes", "region"])
        with patch.object(kraken_api, "_kraken", RegionFake().modules):
            self.assertEqual(main(["kraken", *args, "--api", "python", "--reading-order-model",
                                   str(self.root / "ro.safetensors"), "--reading-order-classes", "region"]), 0)
        details = json.loads((self.root / "out.json").read_text(encoding="utf-8"))["pipeline"][0]["details"]
        self.assertEqual(details["reading_order_classes"], "region")


class KrakenApiCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.image = self.root / "page.png"
        Image.new("RGB", (40, 20), "white").save(self.image)
        for name in ("seg", "rec", "ro"):
            (self.root / f"{name}.safetensors").write_bytes(name.encode())

    def models(self, *extra):
        return [str(self.image), str(self.root / "out.json"), "--segmentation-model",
                str(self.root / "seg.safetensors"), "--recognition-model", str(self.root / "rec.safetensors"),
                *extra]

    def test_cli_api_stays_default_and_rejects_python_only_flags(self):
        with patch("sys.stderr", io.StringIO()):
            for extra in ((), ("--executable", "kraken", "--reading-order-model", "ro.safetensors"),
                          ("--executable", "kraken", "--geometry-output", "g.json")):
                with self.assertRaises(SystemExit):
                    main(["kraken", *self.models(*extra)])

    def test_python_api_writes_prediction_and_geometry(self):
        geometry = self.root / "geometry.json"
        with patch.object(kraken_api, "_kraken", FakeKraken().modules):
            code = main(["kraken", *self.models("--api", "python", "--reading-order-model",
                                                str(self.root / "ro.safetensors"),
                                                "--geometry-output", str(geometry))])
        self.assertEqual(code, 0)
        prediction = json.loads((self.root / "out.json").read_text(encoding="utf-8"))
        self.assertEqual(prediction["text"], "שלום\nHello\nעולם")
        self.assertEqual(json.loads(geometry.read_text(encoding="utf-8"))["input_sha256"],
                         prediction["input"]["sha256"])


@unittest.skipUnless(importlib.util.find_spec("kraken"), "kraken is not installed")
class KrakenLineOrdersBugTests(unittest.TestCase):
    """kraken 7.0.2 `blla.segment`: `line_orders[0]` indexes the pre-sort list, not the returned lines.

    The network steps are stubbed; the reading-order code is kraken's own. With a pre-sort list A, B, C,
    a heuristic order C, A, B and a learned order A, B, C, kraken returns lines C, A, B and
    line_orders [[0, 1, 2]], which reads them C, A, B again: the learned order is lost.
    """

    def test_blla_line_orders_index_the_pre_sort_list(self):
        from kraken import blla

        net = Net("segmentation", {"class_mapping": {"baselines": {"default": 2}, "regions": {}}})
        net.aux_layers = {"ro_model": object()}
        raw = [{"baseline": line.baseline, "boundary": line.boundary, "tags": line.tags} for line in PRE_SORT]
        captured = {}

        def heuristic(lines, regions=None, text_direction="lr"):
            captured["pre_sort"] = list(lines)
            return [2, 0, 1]

        with patch.object(blla, "compute_segmentation_map",
                          lambda *a, **k: {"scale": 1.0, "bounding_regions": None,
                                           "cls_map": {"baselines": {"default": 2}}}), \
                patch.object(blla, "vec_regions", lambda **k: {}), \
                patch.object(blla, "vec_lines", lambda **k: [dict(line) for line in raw]), \
                patch.object(blla, "neural_reading_order", lambda **k: [0, 1, 2]), \
                warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            segmentation = blla.segment(Image.new("RGB", (40, 20), "white"), text_direction="horizontal-rl",
                                        reading_order_fn=heuristic, model=[net])

        def baselines(lines):
            return [line.baseline for line in lines]

        returned = segmentation.lines
        self.assertEqual(baselines(returned), [PRE_SORT[i].baseline for i in (2, 0, 1)])
        self.assertEqual(segmentation.line_orders, [[0, 1, 2]])
        kraken_reading = [returned[i] for i in segmentation.line_orders[0]]
        learned = [captured["pre_sort"][i] for i in (0, 1, 2)]
        self.assertNotEqual(baselines(kraken_reading), baselines(learned))
        self.assertEqual(baselines(kraken_reading), baselines(returned))
        # Mapping through the pre-sort list by line id recovers the learned order.
        fixed = learned_line_order(captured["pre_sort"], returned, [0, 1, 2])
        self.assertEqual(baselines([returned[i] for i in fixed]), baselines(learned))


if __name__ == "__main__":
    unittest.main()
