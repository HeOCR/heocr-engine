# R3 — First trained recognizer

GitHub milestone: `R3 - First trained recognizer`. Label: `roadmap:R3`.

## Objective

Train HeOCR's own Kraken recognition model from scratch on governed synthetic hocrsyngen pages, record every run so that a model hash traces back to its data and settings, and score the model fairly against the R2 baselines.

## Slices

| Notation | Summary | Status |
|---|---|---|
| R3a | Converter from `hocrsyngen_line_annotations.v1` and page images to PAGE XML for ketos, with bidi-consistent training and inference and a deterministic sample-level split; `train-kraken` command; `heocr_engine_training_run.v1` record contract; decision 0007 (from scratch, licence `Needs verification`, blla segmentation) | in progress |
| R3b | Generate a training batch with the hocrsyngen train corpus (seeds disjoint from 101, all four templates), train, and score with blla on the unchanged seed-101 80-page batch against the Tesseract and BiblIA_01 predictions, and on a held-out batch from the eval corpus; oracle-line diagnostic; aggregate numbers and run identities in `docs/baselines.md` | planned; waits for the hocrsyngen line-annotation and corpus work |

## Boundaries

- Trained from scratch; no third-party weights are loaded (decision 0007).
- No weights, images, predictions or training logs are committed, uploaded or published. Release is the maintainer's decision.
- Scores come from hocrgen, on synthetic gold only (decision 0004). Train and test pages share fonts and generator, so R3 numbers say nothing about real pages.
- Offline, deterministic tests with a fake ketos executable; CI does not install Kraken.
