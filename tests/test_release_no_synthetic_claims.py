"""No model card reports anything measured on synthetic data (Shay, 2026-11-20): "Nothing that was reported on synthetic
data stays anywhere in the world." Real held-out sets (PS-v1, NQ1, handwriting) may be reported; synthetic or generated
sets (RC2's generated documents, office_val, D-bench, hocrsyngen batches) may only be named as how a model was chosen.
"""
import re
import unittest
from pathlib import Path

RELEASE = Path(__file__).resolve().parents[1] / "release"
FORBIDDEN = [r"\bRC2\b", r"generated documents?\b.*\b(error|missed|gain|lower|fewer)", r"on synthetic development (scans|sets)",
             r"synthetic office development", r"Tagging matched", r"fewer missed numbers", r"gate-rc2-synth"]


class NoSyntheticClaims(unittest.TestCase):
    def test_cards(self):
        # cards and every NOTICE: heocr bundles NOTICE files in its wheel (pipeline, 2026-11-20)
        for card in sorted([*RELEASE.glob("*/card_body.md"), *RELEASE.glob("*/NOTICE*")]):
            text = card.read_text(encoding="utf-8")
            for pat in FORBIDDEN:
                with self.subTest(card=card.parent.name, pattern=pat):
                    self.assertIsNone(re.search(pat, text, re.I))


if __name__ == "__main__":
    unittest.main()
