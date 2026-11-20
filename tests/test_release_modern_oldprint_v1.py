"""The modern-v1 and oldprint-v1 release packages: files, pins and hygiene (drafts; no DOI yet)."""
import json
import re
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
PINS = {"modern_v1": ("6275943bf68f3d44ecc32f8d4c4195c890c96602111542ebe1f0ae0d8a6a5201", 3704077),
        "oldprint_v1": ("f8090760b5b02d09cf4ddb435e7a5e34089f6f17cde9cfb6c67fd06c6f17ec02", 3628595)}
FILES = {"modern_v1": ["LICENSE", "NOTICE", "card_body.md", "huggingface.yaml", "modern_v1_training_run.json",
                       "zenodo.yaml"],
         "oldprint_v1": ["LICENSE", "NOTICE", "NOTICE.r7", "card_body.md", "huggingface.yaml",
                         "oldprint_v1_training_run.json", "zenodo.yaml"]}


DOIS = {"modern_v1": "10.5281/zenodo.24395010", "oldprint_v1": "10.5281/zenodo.24395013"}  # v3 (no synthetic-data claim, 2026-11-20)

# modern-v1's registered held-out figures (RC2 gate-rc2-synth-r2, PS-v1 print_scan_PS-v1_2026-11-18; benchmarks/results.json)
HELD_OUT_SCORED = {"modern_v1": {"14.1", "14.0", "0.08", "0.74", "1.28"}}  # PS-v1 only: no synthetic figure (Shay, 2026-11-20)


class ReleasePackages(unittest.TestCase):
    def test_files(self):
        for model, names in FILES.items():
            self.assertEqual(sorted(p.name for p in (ROOT / "release" / model).iterdir()), sorted(names))

    def test_pins_agree(self):
        for model, (sha, size) in PINS.items():
            folder = ROOT / "release" / model
            out = json.loads((folder / f"{model}_training_run.json").read_text(encoding="utf-8"))["output"]
            self.assertEqual((out["model_sha256"], out["bytes"]), (sha, size))
            self.assertEqual(out["release_file_name"], f"heocr_{model}.traineddata")
            for name in ("card_body.md", "NOTICE"):
                text = (folder / name).read_text(encoding="utf-8")
                self.assertIn(sha, text)
                self.assertIn(f"{size:,}", text)

    def test_not_published_and_no_test_claims(self):
        for model in PINS:
            folder = ROOT / "release" / model
            record = json.loads((folder / f"{model}_training_run.json").read_text(encoding="utf-8"))
            self.assertFalse(record["model_licence"]["published"])
            self.assertNotIn("DOI-TO-BE-RESERVED", (folder / "card_body.md").read_text(encoding="utf-8"))
            self.assertIn(f"Cite this model by its version DOI: [{DOIS[model]}](https://doi.org/{DOIS[model]}).",
                          (folder / "card_body.md").read_text(encoding="utf-8"))
            body = (folder / "card_body.md").read_text(encoding="utf-8")
            evaluation = body[body.index("## Evaluation"):body.index("## Bias, risks and limitations")]
            if model in HELD_OUT_SCORED:
                # registered held-out runs only (RC2, PS-v1, NQ1; eval 2026-11-20): every figure in Evaluation is one of
                # them, and the generated-document gain never appears without the real-photo result beside it
                figures = set(re.findall(r"\d+\.\d+", evaluation.replace("0.2.0rc1", "")))
                self.assertLessEqual(figures, HELD_OUT_SCORED[model], figures - HELD_OUT_SCORED[model])
                self.assertIn("+0.08 points", body)
            else:
                self.assertRegex(body.lower(), r"not measured on a held-out set (of [a-z ]+ )?yet")
                self.assertIn("HeOCR will score it once in a registered held-out run.", body)
                # held-out figures only (maintainer, 2026-11-19): no dev, tuning or selection figure as performance
                self.assertNotIn("%", evaluation)
                self.assertIsNone(re.search(r"\b\d+\.\d{2,3}\b(?![0-9a-f])", evaluation.replace("5.5.3", "")))
            outside_data = body[:body.index("### Training data")] + body[body.index("### Training procedure"):]
            if model in HELD_OUT_SCORED:
                outside_data = outside_data.replace(evaluation, "")  # Evaluation is checked against the held-out figures
            self.assertIsNone(re.search(r"\d+\.\d+\s*%", outside_data))  # data shares are whole percents

    def test_no_local_paths(self):
        for model in PINS:
            for path in (ROOT / "release" / model).iterdir():
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("/Users/", text, path.name)
                self.assertNotIn("/home/", text, path.name)

    def test_oldprint_carries_r7_notice(self):
        self.assertEqual((ROOT / "release" / "oldprint_v1" / "NOTICE.r7").read_bytes(),
                         (ROOT / "release" / "r7" / "NOTICE").read_bytes())


if __name__ == "__main__":
    unittest.main()
