"""Public card checks for results from registered real held-out sources."""
import re
import unittest
from pathlib import Path

RELEASE = Path(__file__).resolve().parents[1] / "release"
FORBIDDEN = [r"\bRC2\b", r"generated documents?\b.*\b(error|missed|gain|lower|fewer)", r"on synthetic development (scans|sets)",
             r"synthetic office development", r"Tagging matched", r"fewer missed numbers", r"gate-rc2-synth", r"\b(?:PS-v1|NQ1)\b"]


class NoSyntheticClaims(unittest.TestCase):
    def test_cards(self):
        # cards and every NOTICE: heocr bundles NOTICE files in its wheel (pipeline, 2026-11-20)
        for card in sorted([*RELEASE.glob("*/card_body.md"), *RELEASE.glob("*/NOTICE*")]):
            text = card.read_text(encoding="utf-8")
            for pat in FORBIDDEN:
                with self.subTest(card=card.parent.name, pattern=pat):
                    self.assertIsNone(re.search(pat, text, re.I))


def audit_note() -> str:
    body = (RELEASE / "r8b" / "card_body.md").read_text(encoding="utf-8")
    return body.split("### Development reference audit", 1)[1].split("### Text overlap", 1)[0]


class DevelopmentAuditDisclosure(unittest.TestCase):
    def test_r8b_keeps_the_reference_finding_without_development_figures(self):
        note = audit_note()
        for source in ("Kevar", "Brainin", "Yedi'ot ha-Teva"):
            self.assertIn(source, note)
        self.assertIn("one-letter differences", note)
        self.assertNotRegex(note, r"\d")


if __name__ == "__main__":
    unittest.main()
