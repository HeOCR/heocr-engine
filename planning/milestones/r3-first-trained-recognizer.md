# R3 — First trained recognizer

GitHub milestone: `R3 - First trained recognizer`. Label: `roadmap:R3`.

## Objective

Train HeOCR's own Kraken recognition model from scratch on governed synthetic hocrsyngen pages, record every run so that a model hash traces back to its data and settings, and score the model fairly against the R2 baselines.

## Slices

| Notation | Summary | Status |
|---|---|---|
| R3a | Converter from `hocrsyngen_line_annotations.v1` and page images to PAGE XML for ketos, with bidi-consistent training and inference and a deterministic sample-level split; `train-kraken` command; `heocr_engine_training_run.v1` record contract; decision 0007 (from scratch, licence `Needs verification`, blla segmentation) | done (PR #6) |
| R3a1 | Line annotations gain `logical_line_index`, `logical_join` and `occluded` (additive `hocrsyngen_line_annotations.v1` fields): validate them against the manifest's `logical_order`, require left-to-right baselines, train on every physical line including stamp text outside `logical_order`, count occluded lines | done (PR #7) |
| R3b | Generate a training batch with the hocrsyngen train corpus (seeds disjoint from 101, all four templates), train, and score with blla on the unchanged seed-101 80-page batch against the Tesseract and BiblIA_01 predictions, and on a held-out batch from the eval corpus; oracle-line diagnostic; aggregate numbers and run identities in `docs/baselines.md`; the record infers the early-stop reason from the validation history, because ketos 7.0.2 logs none | done (PR #8; results in `docs/baselines.md`) |
| R3c | Retrain R3b's recipe on line polygons rebuilt from the gold baselines by Kraken's polygonizer at the inference height (`--line-polygons kraken --polygonizer-height 1800`); score it with `blla -d horizontal-rl` and Tesseract lines, the oracle paths (d) and (e), hocrgen E2c6 paired accounting against R3b, and hocrgen's mixed-script evaluation fixture; results in `docs/baselines.md` | done (data path PR #13; results in `docs/baselines.md`) |
| R3d | Retrain R3c's recipe on a mixed Hebrew/Latin batch (S10b + S13a train text, seven templates, seed 7101); score it on seed-101, held-out, hocrgen's mixed-script fixture and the held-out eval-mixed-heldout batch (never trained on), with per-script CER and E2c6 paired accounting against R3c; results in `docs/baselines.md` | done (results in `docs/baselines.md`) |
| R3e | Bounded local fine-tune diagnostic on public-authored printed synthetic lines; fixed text/font split, held-out line comparison and offline reproducibility receipt in `research/printed_line_transfer/` | done (PR #21; receipt in `research/printed_line_transfer/README.md`) |
| R3f | Retrain R3d's recipe with typographic punctuation in the training text (dashes, curly quotes, geresh, gershayim and ellipsis); score it on the R3d batches and on eval-typo-heldout and eval-layout-heldout, with a second seed (s7202); results in `docs/baselines.md` | done (PRs #26, #27; results in `docs/baselines.md`) |
| R3g | Train on a per-line mix of crop geometries (`--line-polygons mix`: 1/2 Kraken polygonizer, 1/4 sidecar polygon, 1/4 padded rectangle) to fix R3f's regression on non-Kraken line geometry; results in `docs/baselines.md` | done (PRs #28, #29; results in `docs/baselines.md`) |
| R3h | Re-weight the mix toward Kraken geometry (`--mix-buckets`: 3/4 Kraken, 1/8 sidecar, 1/8 rectangle); recognizer of record and default for every line geometry, including R4d + A1; results in `docs/baselines.md` | done (PRs #30, #31; results in `docs/baselines.md`) |
| R3i | Real-glyph ablation: fine-tune R3h (`train-kraken --base-model`, decision 0013) with an equal line budget and epochs on font-rendered hocrsyngen book pages, on real-glyph pages composed by hocrsyngen `compose-glyph-pages` (S16b), and on a mix; score each on the 38 adjudicated real printed pages with segmentation held fixed, also on the 10 pages from books that gave the glyph bank nothing; an ablation diagnostic under decision 0012 (no arm is selected for release from E2d3d); results in `docs/baselines.md` | done (2026-11-08): on the 10 bank-disjoint pages real-glyph pages beat font pages on every fixed line source (Tesseract lines CER 0.494 → 0.457, mix 0.445); the all-38 gain is 3–4× larger and comes mostly from harvested books; diagnostic only, R3h stays the recognizer of record |

## Boundaries

- Trained from scratch; no third-party weights are loaded (decision 0007).
- No weights, images, predictions or training logs are committed, uploaded or published. Release is the maintainer's decision.
- Scores come from hocrgen, on synthetic gold only (decision 0004).
- Known gold caveat for R3b: in the seed-101 batch, stamp and marginalia text is drawn on the page but missing from `logical_order`, so every engine that reads it is charged with insertions. The batch stays unchanged for comparability with R2a; a separate hocrsyngen slice fixes the gold. Train and test pages share fonts and generator, so R3 numbers say nothing about real pages.
- Offline, deterministic tests with a fake ketos executable; CI does not install Kraken.
