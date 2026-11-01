# R1 — Runtime foundations and plug-in path

GitHub milestone: `R1 - Runtime foundations and plug-in path`. Label: `roadmap:R1`.

## Objective

Make heocr-engine a governed home for local OCR/HTR baselines whose predictions hocrgen can score, and give outside pipelines (preprocessing, recognition, post-correction) a documented way to plug in or submit predictions.

## Slices

| Notation | Summary | Status |
|---|---|---|
| R1a | Governance, planning notation, decision records, and the `heocr_engine_prediction.v1` contract id with optional `pipeline[]` provenance | done (PR #2) |
| R1b | Stage interface (preprocessor, recognizer, post-corrector), subprocess adapter, and `validate-predictions` for predictions-only submissions | done (PR #3) |
| R1c | Kraken baseline from local, hashed segmentation and recognition models | done (PR #4) |

The Tesseract baseline predates this milestone (PR #1) and is the first `recognize` stage.

## Boundaries

- Scoring, normalization profiles, strata and benchmark references stay in hocrgen (hocrgen issue #86; `reference_evaluation.py`).
- Offline, deterministic tests only. No model downloads, no network or proprietary calls (decision 0005).
- No benchmark claims: unit tests use generated pixels and mocked backends.
