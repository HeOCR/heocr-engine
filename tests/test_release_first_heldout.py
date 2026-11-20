"""Held-out figures only (maintainer, 2026-11-19): the first-release kraken cards give no figure as performance.

Evaluation's ruling: none of the six synthetic batches behind R4d, A1 and R3h (seed-101, held-out, eval-mixed-heldout,
eval-typo-heldout, eval-layout-heldout, the hocrgen fixture) is a registered held-out set, so they are development sets.
"""
import re
import unittest
from pathlib import Path

RELEASE = Path(__file__).resolve().parents[1] / "release"
MODELS = ("r4d", "a1", "r3h")
HELD_OUT_SENTENCE = "No held-out score yet; HeOCR will score it once in a registered held-out run."
# figures the cards used to report on development sets
OLD_FIGURES = ("0.020", "0.010", "0.017", "0.009", "0.124", "0.130", "0.168", "0.238", "0.404", "0.498",
               "0.913", "0.915", "0.819", "0.865", "0.9994", "0.9959 ", "reached 0.0", "mean IoU 0.8618")


def figure_hits(body):
    """Every way the card could still present a figure as performance; [] when it does not."""
    hits = []
    if "not measured on a held-out set yet" not in body.lower():
        hits.append("missing: not measured on a held-out set yet")
    if HELD_OUT_SENTENCE not in body:
        hits.append("missing: held-out sentence")
    evaluation = body[body.index("## Evaluation"):body.index("## Bias, risks and limitations")]
    hits += ["% in Evaluation"] * evaluation.count("%")
    hits += re.findall(r"\b\d+\.\d{2,4}\b(?![0-9a-f])", evaluation.replace("7.0.2", ""))
    outside_data = body[:body.index("### Training data")] + body[body.index("### Training procedure"):]
    hits += re.findall(r"\d+\.\d+\s*%", outside_data)  # data shares stay in Training data
    return hits


class FirstReleaseCardsHaveNoDevFigures(unittest.TestCase):
    def test_no_dev_figures_as_performance(self):
        for model in MODELS:
            body = (RELEASE / model / "card_body.md").read_text(encoding="utf-8")
            with self.subTest(model=model):
                self.assertEqual(figure_hits(body), [])
            for figure in OLD_FIGURES:
                with self.subTest(model=model, figure=figure):
                    self.assertNotIn(figure, body)
            with self.subTest(model=model, check="describes, does not measure"):
                self.assertIn("No reviewed real-page evaluation exists.", body)
                self.assertIn("Development sets, not reported as performance.", body)


if __name__ == "__main__":
    unittest.main()
