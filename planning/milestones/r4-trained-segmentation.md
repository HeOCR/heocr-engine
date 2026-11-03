# R4 — Trained segmentation

GitHub milestone: `R4 - Trained segmentation`. Label: `roadmap:R4`.

## Objective

R3b showed that segmentation, not recognition, limits HeOCR's end-to-end accuracy: its recognizer reads true lines almost perfectly but loses most of that with Kraken's default `blla` segmenter. R4 measures where segmentation fails, trains HeOCR's own baseline segmenter on governed synthetic hocrsyngen pages, and scores it end to end against `blla` and Tesseract.

## Slices

| Notation | Summary | Status |
|---|---|---|
| R4a | Segmentation diagnostics: line precision and recall, splits and merges, and reading order against hocrsyngen line annotations; Tesseract-segmentation swap | in progress |
| R4b | `prepare-kraken-data --task segmentation` (PAGE XML with typed regions), `train-kraken-seg` (`ketos segtrain` from scratch) and the segmentation fields of `heocr_engine_training_run.v1`; decision 0008 (from scratch, licence `Needs verification`, typed regions, heuristic reading order) | in review |
| R4c | Train the first segmenter on the R3b training batch; score it with the R3b recognizer end to end on the seed-101 and held-out batches; results in `docs/baselines.md` | in progress |

## Boundaries

- Trained from scratch; no third-party weights are loaded (decision 0008).
- No weights, images, predictions or training logs are committed, uploaded or published. Release is the maintainer's decision.
- Scores come from hocrgen, on synthetic gold only (decision 0004).
- Offline, deterministic tests with a fake ketos executable; CI does not install Kraken.
