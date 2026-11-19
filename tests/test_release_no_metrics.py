"""Held-out figures only (maintainer, 2026-11-19): no release front matter carries a metrics field.

No HeOCR model has a registered held-out score yet, so neither the Zenodo front matter (zenodo.yaml, which becomes
the deposit README's HTRMoPo `metrics`) nor the Hugging Face front matter (`model-index`/`metrics`) may hold one.
"""
import unittest
from pathlib import Path

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
                    # top-level keys only (no yaml dependency, as in CI)
                    keys = {line.split(":", 1)[0] for line in path.read_text(encoding="utf-8").splitlines()
                            if line and not line[0].isspace() and not line.startswith(("#", "-")) and ":" in line}
                    self.assertNotIn("metrics", keys)
                    self.assertNotIn("model-index", keys)


if __name__ == "__main__":
    unittest.main()
