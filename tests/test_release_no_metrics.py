"""Held-out figures only (maintainer, 2026-11-19): no release front matter carries a metrics field.

No HeOCR model has a registered held-out score yet, so neither the Zenodo front matter (zenodo.yaml, which becomes
the deposit README's HTRMoPo `metrics`) nor the Hugging Face front matter (`model-index`/`metrics`) may hold one.
"""
import unittest
from pathlib import Path

import yaml

RELEASE = Path(__file__).resolve().parents[1] / "release"


class NoMetricsInFrontMatter(unittest.TestCase):
    def test_no_metrics(self):
        folders = sorted(p for p in RELEASE.iterdir() if (p / "zenodo.yaml").exists())
        self.assertGreaterEqual(len(folders), 8)
        for folder in folders:
            for name in ("zenodo.yaml", "huggingface.yaml"):
                path = folder / name
                if not path.exists():
                    continue
                with self.subTest(model=folder.name, file=name):
                    front = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    self.assertNotIn("metrics", front)
                    self.assertNotIn("model-index", front)


if __name__ == "__main__":
    unittest.main()
