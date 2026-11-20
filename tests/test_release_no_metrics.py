"""Publication hold and front-matter rules for the archived model cards."""
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

    def test_cards_display_publication_hold_without_download_links(self):
        cards = sorted(RELEASE.glob("*/card_body.md"))
        self.assertEqual(len(cards), 8)
        for card in cards:
            with self.subTest(model=card.parent.name):
                intro = card.read_text(encoding="utf-8").split("\n\n", 2)[1]
                self.assertIn("This model is unpublished.", intro)
                self.assertIn("registered real held-out comparison", intro)
                self.assertIn("beats the state of the art on at least one document type", intro)
                body = card.read_text(encoding="utf-8")
                self.assertNotIn("--download-model", body)
                self.assertNotIn("https://doi.org/10.5281/zenodo.", body)


if __name__ == "__main__":
    unittest.main()
