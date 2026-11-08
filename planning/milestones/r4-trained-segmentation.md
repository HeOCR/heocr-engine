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
| R4d1 | Segmentation line types from regions (`--line-type REGION=TYPE`, for example `stamp_area=stamp`), so that stamp baselines that overlap body lines get their own output channel; the map and per-split counts are recorded; recognition XML is unchanged | done (PR #16) |
| R4d2 | Opt-in `--api python` Kraken stage: in-process segmentation and recognition, a learned line reading order (`ketos rotrain` model) applied correctly despite Kraken 7.0.2's `line_orders` issue, and line geometry output | done (PR #19) |
| R4d | Train the segmenter to completion on sidecar regions with the `stamp` line type, train a line reading-order model on the same pages, and score R4d + R3d end to end (seed-101, held-out, both mixed-script batches) with heuristic and learned order; results in `docs/baselines.md` | done (PR #22) |
| R4e | Reading order beyond line types: RO-v2 (more layouts, line-typed) is a negative result; opt-in region-typed reading-order classes in the `kraken-python` stage (`reading_order_classes: "region"`); results in `docs/baselines.md` (fixture `archive_card` 0.274 → 0.052; no change elsewhere); the clean layout check (eval-layout-heldout, fresh card, ledger and benchmark batch) confirms it: A1 equals gold order (0.122), cards 0.005 / 0.007 against RO-v1's 0.207 / 0.220 | done (stage, PR #23; results, PR #24; clean check, PR #25) |
| R4f1 | Real pages for segmentation training: `pseudo-label-pages` (Tesseract psm 3 lines, unpadded, hOCR baselines, blocks as `body`; a geometry-only page filter against the hand-free strip proxy) writes a `heocr_real_pages.v1` manifest; `train-kraken-seg --real-pages` adds its pages to their splits and records `data.real_pages` (label source and licence, exclusions, licences, counts) | done (PR #55) |
| R4f | Real printed book lines. Step 1, the decomposition on the 38 E2d3d pages: R3h + R4d + A1's +0.661 CER gap to Tesseract is +0.507 segmentation and +0.155 recognition, A1 order adds +0.003; R4d draws word-sized lines (median 165 per page against Tesseract's 27). Step 2 trains a segmenter on hocrsyngen S11c book pages, the governed templates and Tesseract-pseudo-labelled public-domain scans (R4f1), picked on a dev set held out by whole work, and reports on the 38 once | in progress |

## R4f checkpoint selection rule

The lead fixed this rule on 2026-11-08, after the epoch-2 dev numbers and before any later checkpoint's numbers were opened. It is not changed for the rest of the run.

The dev set has 203 pages and none come from E2d3d:

- the two frozen Wikisource Indexes (`ws_index_1715516` and `ws_index_331738`, 60 pages);
- two PBY–NLI books (80 pages);
- ten Reshumot booklets (63 pages).

Page geometry is checked against the hand-free strip proxy; a page is in band when its coverage is between 0.8 and 1.25. Line F1 is measured against Tesseract's lines. `blla` is the comparison throughout.

1. **Primary.** The in-band rate over all 203 pages. Candidates within 0.05 of the best rate count as tied.
2. **Tie-break.** Overall lines per proxy row, closest to 1 wins. If still tied, overall line F1.
3. **Guard.** A candidate is disqualified if, on any pool, its lines per proxy row is more than 1.3 times `blla`'s, or its line F1 is more than 0.10 below `blla`'s. The pools are:
   - each Wikisource Index;
   - each NLI book;
   - Reshumot;
   - the two-column pages.

   The same check is reported for each Reshumot booklet, for information only; it never disqualifies.
4. **Pick.** `blla` is always in the ranking, and the pick is the top of the ranking over `blla` and the candidates that pass the guard. If no R4f checkpoint passes, `blla` stays the default segmenter and is the R4f-round answer on the 38 E2d3d pages. A disqualified model is never scored on E2d3d.

**Why.** E2d3d is all Wikisource. A gain that holds only on Wikisource scans would score well there and fail on other sources, and the guard stops that from shipping. The first such case was epoch 2: on both Wikisource dev Indexes it beat `blla` on in-band rate and line F1. On both NLI books it split printed lines into 3–5 pieces each:

| NLI book | Lines per proxy row (`blla`) | Line F1 (`blla`) |
|---|---:|---:|
| …6440 | 4.81 (1.27) | 0.17 (0.89) |
| …0940 | 3.40 (1.24) | 0.31 (0.96) |

It still led on the primary rate alone, because the strip proxy cannot see horizontal splitting.

## Boundaries

- Trained from scratch; no third-party weights are loaded (decision 0008).
- No weights, images, predictions or training logs are committed, uploaded or published. Release is the maintainer's decision.
- Scores come from hocrgen, on synthetic gold only (decision 0004).
- Offline, deterministic tests with a fake ketos executable; CI does not install Kraken.
