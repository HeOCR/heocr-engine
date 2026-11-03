import copy
import unittest

from heocr_engine.bidi import correct_prediction
from heocr_engine.validate import validate_prediction


def prediction(text="שלום world סוף", track="open"):
    return {"schema_version": "heocr_engine_prediction.v1", "page_id": "sha256:" + "a" * 64,
            "input": {"sha256": "a" * 64, "width": 100, "height": 100}, "track": track,
            "engine": {"name": "fixture", "version": "1"}, "text": text, "words": []}


def geometry(text="שלום world סוף"):
    return {"unit": "pixel", "input_sha256": "a" * 64, "tables": [], "lines": [{"text": text, "bbox": [0, 0, 80, 10],
        "words": [{"text": "שלום", "bbox": [0, 0, 10, 10]},
                  {"text": "world", "bbox": [20, 0, 10, 10]},
                  {"text": "סוף", "bbox": [40, 0, 10, 10]}]}]}


class BidiTest(unittest.TestCase):
    def test_projection_preserves_input_and_proprietary_track(self):
        original = prediction(track="proprietary")
        saved = copy.deepcopy(original)
        result, report = correct_prediction(original, geometry())
        self.assertEqual(original, saved)
        self.assertEqual(result["text"], "סוף world שלום")
        self.assertEqual(result["track"], "proprietary")
        self.assertEqual(result["pipeline"][0]["track"], "proprietary")
        self.assertEqual(report["changed_lines"], 1)
        self.assertEqual(validate_prediction(result)[0], [])
        stage = result["pipeline"][-1]
        self.assertEqual({a["role"] for a in stage["artifacts"]}, {"implementation", "geometry"})
        self.assertTrue(all(len(a["sha256"]) == 64 for a in stage["artifacts"]))
        self.assertEqual(len(stage["config_sha256"]), 64)
        altered = geometry()
        altered["tables"].append({"bbox": [90, 90, 1, 1]})
        self.assertNotEqual(stage["artifacts"][1]["sha256"],
                            correct_prediction(original, altered)[0]["pipeline"][-1]["artifacts"][1]["sha256"])

    def test_wrong_image_geometry_abstains(self):
        p = prediction()
        g = geometry()
        g["input_sha256"] = "b" * 64
        out, report = correct_prediction(p, g)
        self.assertEqual(out, p)
        self.assertEqual(report["reason"], "missing_or_invalid_geometry")

    def test_missing_or_invalid_geometry_abstains(self):
        for g in (None, {}, {"unit": "pixel", "lines": []},
                  {"unit": "inch", "lines": [], "tables": []}):
            out, report = correct_prediction(prediction(), g)
            self.assertEqual(out, prediction())
            self.assertEqual(report["reason"], "missing_or_invalid_geometry")

    def test_hazards_abstain(self):
        cases = []
        for text in ("שלום 3 world סוף", "שלום לא world סוף", "שלום world hello סוף"):
            g = geometry(text)
            g["lines"][0]["words"] = [{"text": token, "bbox": [i * 12, 0, 10, 10]}
                                           for i, token in enumerate(text.split())]
            cases.append((prediction(text), g))
        g = geometry(); g["tables"] = [{"bbox": [0, 0, 2, 2]}]; cases.append((prediction(), g))
        g = geometry(); g["lines"][0]["words"][1]["bbox"] = [9, 0, 10, 10]; cases.append((prediction(), g))
        cases.append((prediction("שלום world סוף\nשלום world סוף"), geometry()))
        for p, g in cases:
            self.assertEqual(correct_prediction(p, g)[0], p)

    def test_one_pixel_tolerance_and_beyond(self):
        g = geometry(); g["lines"][0]["bbox"] = [1, 1, 48, 8]
        self.assertEqual(correct_prediction(prediction(), g)[1]["changed_lines"], 1)
        g["lines"][0]["bbox"] = [2, 2, 46, 6]
        self.assertEqual(correct_prediction(prediction(), g)[1]["changed_lines"], 0)


if __name__ == "__main__":
    unittest.main()
