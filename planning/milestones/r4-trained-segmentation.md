# R4 — Trained segmentation

GitHub milestone: `R4 - Trained segmentation`. Label: `roadmap:R4`.

## Objective

R3b showed that segmentation, not recognition, limits HeOCR's end-to-end accuracy: its recognizer reads true lines almost perfectly but loses most of that with Kraken's default `blla` segmenter. R4 measures where segmentation fails, trains HeOCR's own baseline segmenter on governed synthetic hocrsyngen pages, and scores it end to end against `blla` and Tesseract.

## Slices

| Notation | Summary | Status |
|---|---|---|
| R4a | `diagnose-segmentation`: line precision and recall, splits and merges, and reading order against hocrsyngen line annotations; error decomposition of R3b + `blla` (order, line finding, crop geometry); segmenter swap (`blla -d horizontal-rl`, Tesseract lines, Kraken legacy boxes); results in `docs/baselines.md` | in review (PR #10) |
| R4b | `prepare-kraken-data --task segmentation` (PAGE XML with typed regions), `train-kraken-seg` (`ketos segtrain` from scratch) and the segmentation fields of `heocr_engine_training_run.v1`; decision 0008 (from scratch, licence `Needs verification`, typed regions, heuristic reading order) | done (PR #9) |
| R4b1 | Segmentation data uses the sidecar's region polygons (hocrsyngen S11a page `regions`) when every page has them (`region_geometry: "sidecar"`), validated against the lines; line bounding boxes stay the fallback; recognition XML ignores them | done (PR #11) |
| R4c | Train the first segmenter on the R3b training batch; score it with the R3b recognizer end to end on the seed-101 and held-out batches; results in `docs/baselines.md` | paused (partial): stopped after 2 epochs so the recognizer retrain (R3c) could take the training slot. Line geometry of the epoch-1 model against `blla` (polygon F1 0.911 / 0.899 against 0.765 / 0.671, seed-101 / held-out) is in `docs/baselines.md`. A full run on sidecar regions, if any, is a later slice (R4d) |
| S11a | hocrsyngen, cross-repo: region polygons in the line-annotations sidecar, an additive `hocrsyngen_line_annotations.v1` field, so segmenters can train and be checked on region geometry | done (hocrsyngen PR #76) |

## Boundaries

- Trained from scratch; no third-party weights are loaded (decision 0008).
- No weights, images, predictions or training logs are committed, uploaded or published. Release is the maintainer's decision.
- Scores come from hocrgen, on synthetic gold only (decision 0004).
- Offline, deterministic tests with a fake ketos executable; CI does not install Kraken.
