# 0002 — Normalization belongs to the evaluator

- Status: accepted
- Date: 2026-11-01
- Decided by: HeOCR team lead, under delegation from the maintainer

## Decision

Normalization profiles are allowed only as explicit, recorded transforms applied to both prediction and reference. The primary profile is NFC + bidi control characters stripped + whitespace folded. A `consonantal` profile (niqqud and cantillation removed) is reported alongside. `punct_folded` is report-only. These profiles are implemented in hocrgen's evaluator, not here.

## Consequences for this repository

- `heocr_engine_prediction.v1` text is raw engine output in Unicode logical order. Engines and stages must not normalize, reorder or strip it, and the contract makes no normalization assumption.
- A post-correction stage that deliberately changes text is a recorded `postcorrect` stage in `pipeline[]`, not a hidden normalization.
