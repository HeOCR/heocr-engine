# Baselines

Both baselines run locally with user-supplied engines and models. Nothing is downloaded, and each prediction records executable and model hashes. The hashes help with provenance but do not guarantee identical results across machines or library versions. Neither baseline comes with an accuracy claim. Scoring happens in hocrgen, and for now the reported number is synthetic gold (planning decision 0004).

## Tesseract

`heocr-engine tesseract IMAGE OUT --executable … --tessdata-dir …` (see the README). It is open track, records the executable, models and `psm`, and outputs word boxes and confidences.

## Kraken

```sh
heocr-engine kraken page.png prediction.json \
  --executable /path/to/kraken \
  --segmentation-model /path/to/blla.mlmodel \
  --recognition-model /path/to/BiblIA_01.mlmodel
```

- Install Kraken with the optional extra, `pip install 'heocr-engine[kraken]'` (tested with kraken 7.0.2), or point `--executable` at an existing install. The core package and CI do not need it. It runs `segment -bl` (baseline segmentation), then `ocr --reorder --base-dir R`, so the text comes out in Unicode logical order with a right-to-left base direction. Use `--base-dir auto` or `L` for other material.
- **Line order:** the segmentation direction follows `--base-dir` (decision 0009):
  - `R`, the default, runs `segment -bl -d horizontal-rl`, so lines that share a row are read right to left;
  - `L` runs `-d horizontal-lr`;
  - `auto` passes no `-d`, which leaves Kraken's own default (`horizontal-lr` in 7.0.2).

  `--text-direction` (or `"text_direction"` in a pipeline config) overrides it. The direction is in the stage `details` (`null` for Kraken's default) and in its `config_sha256`. **R2a and R3b predictions predate this option and used `horizontal-lr`**; their stage details have no `text_direction`. In R4a, `horizontal-rl` lowered R3b + `blla` overall CER from 0.286 to 0.255 (seed-101) and from 0.405 to 0.358 (held-out).
- The prediction has one `recognize` stage named `kraken`. Its artifacts are the executable, `model:segmentation` and `model:recognition` hashes.
- `words` is empty: Kraken's plain-text output has no word geometry.
- The default timeout is 600 seconds per call, up to a maximum of 3600, because CPU inference on a full page can be slow.
- In a pipeline config: `{"type": "kraken", "executable": "…", "segmentation_model": "…", "recognition_model": "…", "base_dir": "R", "text_direction": "horizontal-rl"}`.
- **Known issue, Kraken 7.0.2 on macOS:** Kraken occasionally crashes on exit after it has written its output (stderr shows `libc++abi` … `recursive_mutex lock failed`) and exits non-zero. In the first 80-page run this happened once in 82 page runs. heocr-engine fails closed and reports `Kraken failed with exit status …`, even though an output file exists; this is intended, because a crashed process gives no guarantee that its output is complete. Retry the page. Do not wrap Kraken so that non-zero exits are accepted.

Reference models, verified 2026-11-01 and recorded in [decision 0006](../planning/decisions/0006-model-licences.md). Pin runs by model sha256 and version DOI, never by concept DOI:

| Model | Version DOI | Licence | sha256 |
|---|---|---|---|
| `blla.mlmodel` (baseline segmentation, 2025-01-06) | 10.5281/zenodo.14602569 | Apache-2.0 | `77a638a83c9e535620827a09e410ed36391e9e8e8126d5796a0f15b978186056` |
| `BiblIA_01.mlmodel` (medieval Hebrew bookhand) | 10.5281/zenodo.5468286 | CC-BY-SA-4.0 | `bb48c481d8c46b41465920482e253dc990163405c584d24700cfb0d9b4ca9147` |

Attribution: BiblIA_01, Medieval Hebrew manuscripts version 1.0, by Daniel Stökl Ben Ezra, licensed CC BY-SA 4.0, doi:10.5281/zenodo.5468286. heocr-engine does not redistribute either model. 
**Needs verification:** whether CC BY-SA 4.0's ShareAlike reaches predictions (output text) made with BiblIA_01 is unresolved, and no claim is made either way. Until it is settled, predictions made with BiblIA_01 that HeOCR publishes or commits carry the attribution above, and their licence is left to the maintainer's decision.

The stage record's `license: "Apache-2.0"` describes the Kraken engine only. Model licences follow from the `model:segmentation` and `model:recognition` hashes in `artifacts`, matched against the table above, not from that field.

BiblIA_01 was trained on medieval manuscripts. On modern cursive it recognizes little. In a local smoke run on a public-domain 1892 manuscript page it produced only scattered characters. Treat it as a floor and a check that the pipeline works, not as a target. The segmentation concept DOI (10.5281/zenodo.14602568) resolves to its newest version, so it does not identify a model.

## First results: synthetic gold (2026-11-01)

The first end-to-end run scored both baselines with hocrgen `evaluate-references` on the hocrsyngen S8j batch: 80 synthetic pages, 20 from each of four templates. CER is character error rate and WER is word error rate; lower is better. `primary.v1` is the headline profile.

| Profile | Tesseract CER / WER | Kraken CER / WER |
|---|---|---|
| `raw.v1` | 0.403 / 0.610 | 0.429 / 0.801 |
| **`primary.v1`** | **0.379 / 0.610** | **0.428 / 0.801** |
| `consonantal.v1` | 0.376 / 0.607 | 0.425 / 0.801 |

By template, `primary.v1` CER / WER:

| Template | Tesseract | Kraken |
|---|---|---|
| `printed_letter` | 0.184 / 0.321 | 0.344 / 0.651 |
| `printed_letter_heavy_scan` | 0.145 / 0.266 | 0.382 / 0.681 |
| `handwritten_note` | 0.648 / 1.018 | 0.516 / 0.969 |
| `handwritten_note_heavy_wear` | 0.665 / 1.006 | 0.507 / 0.977 |

Against Tesseract as the baseline set, Kraken's whole-set ΔCER is +0.049 and ΔWER is +0.192 on `primary.v1`. The two runs use different pipelines, so hocrgen reports the delta for the whole set and does not credit it to a single stage. Tesseract is much stronger on the printed templates; Kraken with BiblIA_01 is stronger on the handwriting-style ones. A WER above 1.0 means the engine produced more words than the reference contains.

Run identities:

| Part | Identity |
|---|---|
| heocr-engine | `a941b18990fb04c4414dfdec9e2fe24df9fdd5fe` (R1 complete, version 0.2.0) |
| hocrgen | `cbfa87bbe57f8f2a88be81387a454d94c965d294` (hocrgen 0.1.0, `hocrgen_reference_evaluation_run.v1`) |
| Reference set | hocrsyngen S8j batch, seed 101, manifest sha256 `9b6e54f798fc6d131431e114716b2db12018c3bc4726369b4c749a7237182d20` (`synthetic_gold:9b6e54f798fc6d13`), checked as `public_manifest_page_checksums` |
| Page mapping | `hocrgen_reference_page_mapping.v1` from asset sha256, sha256 `181bc78dcf95a03e9256af4c91b39a3d0cb4dc0f4f7446aee760a28ee3130cc7`; 80 of 80 pages mapped |
| Tesseract predictions | Tesseract 5.5.3, `heb` traineddata, `--psm 3`; prediction-set sha256 `9f1c36d536e22bc9cb42a6dafd84fad5382768c3d03882cdb24f76fa1f2ab617` |
| Kraken predictions | Kraken 7.0.2, `blla` + `BiblIA_01` (hashes in the model table above), `--base-dir R`; prediction-set sha256 `bd546828a82f69eeee1fb4c4ecf2186c7271b9b1ff2760e87bc11be676f0dcec` |

Both runs are open track. The prediction files, page images and hocrgen reports are not in this repository.

Limits:

- **Synthetic only.** The reference text is generated, so it is exact, but the pages are not real documents.
- **Handwriting-style font, not handwriting.** The `handwritten_*` templates are rendered with a handwriting-style font. They do not measure real handwritten text recognition.
- **One batch, one seed, no confidence intervals.** Small differences between engines or profiles are not established.
- **No claim about real pages.** These numbers say nothing about HASH scans, tender pages or other real material (decision 0004). Real pages remain `unreviewed` diagnostics until references with evidence exist.

## R3b: first trained recognizer, synthetic gold (2026-11-02)

R3b is HeOCR's first own Kraken recognition model. It was trained from scratch on synthetic hocrsyngen pages ([decision 0007](../planning/decisions/0007-first-trained-recognizer.md)), and run with the same `blla` segmentation and Kraken 7.0.2 as the BiblIA_01 baseline: `heocr-engine kraken … --recognition-model best_0.9985.safetensors --base-dir R`. Against BiblIA_01, hocrgen attributes the delta to one stage, the recognition model being replaced. The weights are not in this repository and are not published; their licence is `Needs verification`.

**Seed-101 images, S10c gold (headline).** These are the same 80 page images as R2a, scored against the corrected S10c gold, which includes stamp and marginalia text. `primary.v1` CER / WER:

| Template | R3b | Tesseract | Kraken + BiblIA_01 |
|---|---|---|---|
| `printed_letter` | 0.267 / 0.494 | 0.111 / 0.232 | 0.261 / 0.567 |
| `printed_letter_heavy_scan` | 0.377 / 0.701 | 0.122 / 0.230 | 0.308 / 0.602 |
| `handwritten_note` | 0.208 / 0.438 | 0.641 / 0.998 | 0.509 / 0.953 |
| `handwritten_note_heavy_wear` | 0.261 / 0.567 | 0.658 / 0.994 | 0.506 / 0.962 |
| **overall** | **0.286 / 0.558** | **0.338 / 0.553** | **0.377 / 0.742** |

- **Deltas (R3b minus baseline, 80 common items):**
  - against Tesseract, ΔCER −0.052 and ΔWER +0.004;
  - against BiblIA_01, ΔCER −0.091 and ΔWER −0.184.
- **Other profiles, overall CER (R3b / Tesseract / BiblIA_01):** `raw.v1` 0.286 / 0.352 / 0.378; `consonantal.v1` 0.283 / 0.336 / 0.375.
- **S8j gold, the R2a table above:** R3b scores 0.299 / 0.581 overall, against 0.379 / 0.610 and 0.428 / 0.801. By template: 0.314 / 0.555, 0.388 / 0.740, 0.206 / 0.430 and 0.254 / 0.560.

**Held-out batch.** 80 new pages, 20 per benchmark template, with text from the hocrsyngen eval corpus (disjoint from the training corpus). `primary.v1` CER / WER:

| Template | R3b | Tesseract |
|---|---|---|
| `printed_letter` | 0.408 / 0.657 | 0.102 / 0.189 |
| `printed_letter_heavy_scan` | 0.519 / 0.841 | 0.138 / 0.218 |
| `handwritten_note` | 0.312 / 0.585 | 0.687 / 0.976 |
| `handwritten_note_heavy_wear` | 0.334 / 0.628 | 0.663 / 0.976 |
| **overall** | **0.404 / 0.688** | **0.353 / 0.535** |

R3b minus Tesseract is ΔCER +0.051 and ΔWER +0.153.

**Oracle-line diagnostic.** This isolates recognition from segmentation. Kraken recognizes the true line polygons and baselines, and the output is compared after NFC normalization only; it is not a hocrgen score. It runs on cpu from PAGE XML in logical order, so it is not identical to ketos's own validation (mps, arrow, display order): on the validation split it counts 42 character errors where ketos counted 23 for the same weights. CER / WER:

| Template | Held-out batch | R3b validation split |
|---|---|---|
| `printed_letter` | 0.006 / 0.013 | 0.002 / 0.008 |
| `printed_letter_heavy_scan` | 0.002 / 0.008 | 0.002 / 0.005 |
| `handwritten_note` | 0.012 / 0.034 | 0.018 / 0.041 |
| `handwritten_note_heavy_wear` | 0.015 / 0.045 | 0.004 / 0.017 |
| `archive_card` / `archive_card_faded_scan` | — | 0.000 / 0.000 |
| `ledger` | — | 0.002 / 0.003 |
| overall | 0.008 / 0.023 (643 lines) | 0.003 / 0.008 (1,553 lines) |

**Reading.**
- **Segmentation dominates the end-to-end error.** On the true lines, recognition error is about 1%. End to end it is 29–40%. `blla` splits lines into fragments and mixes their order, and recognition on its crops is weaker than on the training polygons.
- **By template:** R3b is much better than both baselines on the handwriting-style templates and much worse than Tesseract on the printed ones. Tesseract's own layout analysis copes with printed pages far better.
- **No overall ranking against Tesseract.** R3b's overall CER beats Tesseract's on the seed-101 images (0.286 against 0.338) but loses on the held-out batch (0.404 against 0.353). The overall figure depends on the template mix and the text, so only the per-template differences are robust.
- **Next lever:** improving segmentation is the next step for this pipeline, more than recognition.
- **Real scans:** on the 10-page `unreviewed` real-scan sanity check, R3b reads almost nothing (`consonantal.v1` CER 0.890 against BiblIA_01's 0.895). This is a diagnostic only, never a result (decision 0004).

Run identities:

| Part | Identity |
|---|---|
| heocr-engine | `37f952f` (R3a1, version 0.2.0) for training and inference |
| hocrsyngen | `bbcaf0e` (S10c) for the training and held-out batches |
| hocrgen | `2d3efb0` (hocrgen 0.1.0); all six sets were rescored with it, and the R2a S8j numbers reproduce exactly |
| Training batch | Seed 5101, 1,800 pages over all 7 templates, train corpus sha256 `a3f2f0db1bf48d8cdd618579af42ca36710cadf81cdc4d5e89d2dc6c192e6611`. Manifest `29dffcca283770c56dedb4e53b57ccae289ec37124fd4399d968d93a3dd9295a`, line annotations `5d1155cff7f17044e7035ef831718ad55e4880766908c3e0c3a11f50a81f71d0` |
| Split | By sample, split seed 0, 5%: train 1,710 pages / 27,487 lines, validation 90 pages / 1,553 lines |
| Training | ketos 7.0.2 default VGSL spec, from scratch, `--augment`, batch 16, lr 0.001, AdamW, constant schedule. Early stopping with lag 3 and min-epochs 5. mps, seed 42, not deterministic. Stopped after 12 epochs; best epoch 8, val_accuracy 0.9985 (kraken-internal, display order) |
| Model | `best_0.9985.safetensors`, sha256 `0b5a0c3c0d66599095068f94234e86f563e17182a34b863d7e4941ef54b9e362`; licence `Needs verification`, unpublished |
| Seed-101 references | S10c gold, manifest `c4b4ca4ed5b92080c0a4d13c4fa2da505080da11b37203ecb0d4fa1bcb164ec3`; S8j gold, `9b6e54f7…` as above; mapping `181bc78d…` as above |
| Held-out references | Seed 6101, eval corpus sha256 `89e52f8b90cdbb8a276fbdaf96530afff2cc266e13ad6355c215c79e5a58d97f`, manifest `d6ed102d8ef7787d03b400776924354bebfadd5af482d0e1cbe03de89724c7c1`, mapping `dc4537d46ec9886224244199e32f4468a674cfd38d35c6398585f11347f5210a` |
| R3b predictions | Seed-101 `8542f76dc07a005fd0b747e7c5c929ca2e069a7336227538d5268244e02ae8fe`; held-out `07bd0d1741c250309ff32f22f3dad906bc2031a0f2de998909660c17234b2aa9` |
| Tesseract predictions | Seed-101: the R2a set `9f1c36d5…`. Held-out: `21ac20191797f4f93fa9bd467763be6c13c459c5f33c3c95604ec9cfdf328d48`, same binaries and `--psm 3` |
| BiblIA_01 predictions | Seed-101: the R2a set `bd546828…` |

Limits (in addition to those above):

- **Same generator for training and test.** The model has seen every font, template and degradation preset it is scored on; only the text differs. These numbers measure in-distribution synthetic performance.
- **One training run and one seed per batch.** There are no confidence intervals.
- **Agent-authored corpora.** The training and evaluation text was written by the project (hocrsyngen S10b), not drawn from real documents.
- **The validation split selected the checkpoint** and was not used as a test set. The held-out batch and the seed-101 images were not seen in training.

## R4a: where R3b's end-to-end error comes from (2026-11-03)

R4a splits R3b's end-to-end error into reading order, line finding and recognition on predicted crops, and tries other line segmenters in front of the unchanged R3b recognizer. Line geometry is checked with [`heocr-engine diagnose-segmentation`](segmentation_diagnostic.md). Text is scored with hocrgen `evaluate-references` (`primary.v1`). Same batches, gold and model as R3b: the seed-101 images against S10c gold, and the held-out s6101 batch.

Rows marked *diagnostic* use gold line geometry or gold order, so no real pipeline can produce them. They bound what each fix could gain; they are not results. Real pipelines are marked *pipeline*.

### Decomposition (`primary.v1` CER, overall)

| Step | Lines | Order | Kind | Seed-101 | Held-out |
|---|---|---|---|---|---|
| (a) R3b + `blla`, as in R3b | `blla` | `blla` | pipeline | 0.286 | 0.405 |
| (b) `blla` lines re-sorted into gold order | `blla` | gold | diagnostic | 0.231 | 0.317 |
| (c) true lines, in `blla`'s order | gold | `blla` | diagnostic | 0.050 | 0.124 |
| (e) true baselines, Kraken's own polygons | gold baselines | gold | diagnostic | 0.224 | 0.279 |
| (d) true lines and order (oracle) | gold | gold | diagnostic | 0.013 | 0.008 |

- **(b)**: each predicted line is anchored to the gold line it lies in most. Fragments of one gold line are then ordered right to left.
- **(c)**: each true line takes the position of its one-to-one `blla` partner, or of the first `blla` line anchored to it.
- **(e)**: Kraken's polygonizer (`calculate_polygonal_environment`, the step that turns `blla` baselines into line polygons) is run on the true baselines.
- **(d)**: R3's oracle path, joined into pages and scored by hocrgen.
- Newlines join physical lines throughout. Wrapped lines therefore cost one character against gold, as they do for any engine.

Reading:

- **Reading order costs about 0.04–0.12 CER.** It is the (a)→(b) step (0.055 / 0.088), or (c) against (d) (0.037 / 0.116).
- **Recognition on Kraken-made crops is the largest single cost.** On `blla` lines that match a true line one-to-one (polygon IoU ≥ 0.5), R3b's line CER is 0.211 on seed-101 and 0.267 on held-out; on the true crops of the same lines it is 0.009 and 0.008. Two swaps on the matched held-out lines locate the cause:
  - `blla` baselines with the true polygons give a line CER of 0.012 (seed-101 0.014);
  - true baselines with `blla` polygons give 0.275.
  `blla`'s baselines are fine; the polygons Kraken builds around them are what R3b cannot read.
- **A perfect baseline segmenter would not fix this on its own.** Step (e) gives every line its true baseline and Kraken's own polygon, in gold order, and still scores 0.224 / 0.279. Kraken recomputes polygons from the baselines at inference, so a newly trained baseline segmenter would feed R3b the same kind of crop.
- R3b was trained only on hocrsyngen's own line polygons. On `printed_letter*`, Kraken's polygons are about 1.3–1.5× taller (median, matched lines). On the handwriting-style templates they are about the same height and still poorly read, so the difference is in polygon shape, not only scale.
- **Line finding proper (splits, misses) is the smaller part,** roughly (b) against (e).

### Line geometry (`diagnose-segmentation`, polygon IoU ≥ 0.5)

| Segmenter | Batch | P / R / F1 | Split gold lines | Merging predicted lines (gold lines merged) | Missed | Spurious | Kendall τ | Adjacent pairs kept |
|---|---|---|---|---|---|---|---|---|
| `blla` | seed-101 | 0.733 / 0.800 / 0.765 | 78 | 16 (32) | 27 | 1 | 0.843 | 0.831 |
| `blla` | held-out | 0.624 / 0.726 / 0.671 | 96 | 4 (8) | 28 | 0 | 0.676 | 0.773 |
| `blla -d horizontal-rl` | seed-101 | same lines | | | | | 0.838 | 0.866 |
| `blla -d horizontal-rl` | held-out | same lines | | | | | 0.811 | 0.858 |
| Tesseract `--psm 3` lines | seed-101 | 0.837 / 0.688 / 0.755 | 1 | 61 (162) | 41 | 20 | 1.000 | 1.000 |
| Tesseract `--psm 3` lines | held-out | 0.902 / 0.728 / 0.805 | 1 | 39 (111) | 63 | 7 | 0.995 | 0.992 |
| Kraken legacy boxes (`segment -x -d horizontal-rl`) | seed-101 | 0.887 / 0.628 / 0.736 | 7 | 34 (71) | 174 | 16 | 0.973 | 0.978 |
| Kraken legacy boxes (`segment -x -d horizontal-rl`) | held-out | 0.741 / 0.565 / 0.641 | 4 | 17 (41) | 158 | 24 | 0.997 | 0.997 |

Gold lines: 640 (seed-101) and 643 (held-out). With baseline matching instead (`--match baseline`), `blla`'s F1 is 0.842 / 0.773 and Tesseract's 0.801 / 0.816, so the polygon rule is the stricter one for `blla`.

- **`blla`:** splits title and body lines into fragments (held-out: 41 of 283 body lines, 7 of 80 titles). It handles stamps and margin notes poorly. With Kraken's default `-d horizontal-lr`, it also orders lines that share a row left to right: the three signature boxes and the fragments of a split line. `-d horizontal-rl` fixes that part of the order.
- **Tesseract:** joins the three signature boxes into one line and misses most rotated stamp text. Otherwise its order is almost perfect.

### Segmenter swap, end to end (`primary.v1` CER / WER, pipeline)

Every row but the last uses the R3b recognizer, via `kraken -f page ocr --reorder --base-dir R` on the given lines.
- **Tesseract lines:** `tesseract --psm 3 hocr` with the R2 binary and `heb` model. Line boxes become rectangular polygons, and hOCR baselines are kept. Tesseract's text is discarded.
- **Legacy boxes:** come with no baselines, and Kraken's PAGE reader drops baseline-less lines for a baseline-trained model. A horizontal baseline is therefore placed at 0.8 of the box height. This is a heuristic.

| Template | R3b + `blla` | R3b + `blla -d horizontal-rl` | R3b + Tesseract lines | R3b + legacy boxes | Tesseract alone |
|---|---|---|---|---|---|
| **Seed-101, S10c gold** | | | | | |
| `printed_letter` | 0.267 / 0.495 | 0.214 / 0.447 | 0.220 / 0.339 | 0.266 / 0.483 | **0.111 / 0.232** |
| `printed_letter_heavy_scan` | 0.377 / 0.701 | 0.327 / 0.657 | 0.293 / 0.489 | 0.284 / 0.495 | **0.122 / 0.230** |
| `handwritten_note` | 0.208 / 0.438 | 0.212 / 0.433 | **0.111 / 0.266** | 0.131 / 0.266 | 0.641 / 0.998 |
| `handwritten_note_heavy_wear` | 0.261 / 0.567 | 0.254 / 0.559 | 0.181 / 0.412 | **0.134 / 0.305** | 0.658 / 0.994 |
| overall | 0.286 / 0.558 | 0.255 / 0.529 | **0.211 / 0.383** | 0.216 / 0.403 | 0.338 / 0.553 |
| **Held-out s6101** | | | | | |
| `printed_letter` | 0.408 / 0.653 | 0.330 / 0.612 | 0.168 / 0.317 | 0.343 / 0.646 | **0.102 / 0.189** |
| `printed_letter_heavy_scan` | 0.521 / 0.843 | 0.457 / 0.787 | 0.212 / 0.383 | 0.469 / 0.806 | **0.138 / 0.218** |
| `handwritten_note` | 0.312 / 0.585 | 0.304 / 0.575 | **0.095 / 0.186** | 0.146 / 0.289 | 0.687 / 0.976 |
| `handwritten_note_heavy_wear` | 0.334 / 0.628 | 0.314 / 0.613 | **0.149 / 0.327** | 0.167 / 0.353 | 0.663 / 0.976 |
| overall | 0.405 / 0.687 | 0.358 / 0.654 | **0.162 / 0.311** | 0.301 / 0.553 | 0.353 / 0.535 |

The R3b + `blla` column is this run's re-run of R3b's pipeline, with PAGE XML output so that line geometry is kept. It reproduces R3b's text on 156 of 160 pages; the other four differ by a few characters. The scores match R3b's table to ±0.004.

- **R3b with Tesseract's lines beats R3b + `blla` on every template on both batches,** and has the best overall CER of any pipeline here: 0.211 and 0.162, against Tesseract's 0.338 and 0.353.
- **It does not beat Tesseract on every template.** On the printed templates Tesseract alone stays clearly ahead (for example 0.102 against 0.168 on held-out `printed_letter`). On a printed page R3b + Tesseract lines is worse than Tesseract; on a handwriting-style page it is far better.
- **Recognition on Tesseract crops is still well short of the oracle:** matched-line CER 0.109 (seed-101) and 0.081 (held-out), against about 0.01. Rectangles suit R3b better than Kraken's polygons, but not as well as its training polygons. Rebuilding Tesseract lines with Kraken's polygonizer (Tesseract baselines + Kraken polygons) loses most of the gain: 0.271 / 0.323 overall.
- **`-d horizontal-rl` is a free fix for the existing pipeline:** −0.031 and −0.047 overall CER, mostly on the printed templates. It is one flag on `segment -bl` and changes order only.
- **Not a fix:** replacing `blla`'s polygons by their bounding boxes is worse, 0.333 / 0.382. The legacy box segmenter helps the handwriting-style templates but misses about a quarter of all lines.

### What this means for R4b and R4c

1. **The largest lever is the recognizer's crop geometry, not baseline detection.** Train or fine-tune the recognizer on the line polygons it will meet at inference: polygons rebuilt by Kraken's polygonizer from the true baselines, at least as augmentation. Re-measure (e), which would show it directly. Otherwise a segmenter trained in R4c is capped near step (e), 0.22–0.28 overall, however good its baselines.
2. **Reading order is the second lever, about 0.04–0.12.** `-d horizontal-rl` recovers part of it now. The rest comes from fragments and from where stamps and margin notes fall. Region geometry (S11a) and an order model are the targets here. Tesseract's τ ≈ 1.0 shows that the page layouts are simple enough.
3. **Line finding proper is the smallest part.** `blla` splits about 12–15% of gold lines. A trained segmenter should cut splits and stamp/margin misses, and these are easiest to check with `diagnose-segmentation` before any recognition.
4. **A cheap interim pipeline:** Tesseract line finding + R3b is a strict improvement over `blla` + R3b everywhere. It is not a replacement for Tesseract on printed pages.

### Run identities

| Part | Identity |
|---|---|
| heocr-engine | `b90a160` (this PR's `diagnose-segmentation`); R3b inference as in R3b (`37f952f`) |
| hocrgen | `2d3efb0` (hocrgen 0.1.0) |
| Kraken | 7.0.2 on cpu; `blla` sha256 `77a638a83c9e5356…` (table above); R3b `0b5a0c3c0d665990…` |
| Tesseract | 5.5.3, executable `d3d15b31535c2dd8…`, `heb` `11f9e43ab227f786…`, `--psm 3` (the R2 binaries) |
| Seed-101 | S10c gold, manifest `c4b4ca4ed5b92080…`, line annotations `39f67296970f7fca5c9c813440665669342b9586dc207daf601a7ce54160550d` (hocrsyngen `bbcaf0e`, S10c run). Images are byte-identical to the S8j/R2a batch (all 80 sha256 match) |
| Held-out | Manifest `d6ed102d8ef7787d…`, mapping `dc4537d4…` (as R3b) |
| Prediction sets, seed-101 | (a) `b560e25d…`, `-d horizontal-rl` `cc63ae6b…`, Tesseract lines `95ebba66…`, legacy `d485fcb7…`, (b) `fbf5da69…`, (c) `c800f40f…`, (d) `0a41ac08…`, (e) `81946e34…` |
| Prediction sets, held-out | (a) `6d71ebf2…`, `-d horizontal-rl` `b5847b78…`, Tesseract lines `729b8fff…`, legacy `6416170e…`, (b) `f989d301…`, (c) `c1e37534…`, (d) `71ac606e…`, (e) `9936af98…` |
| Line-file sets (`diagnose-segmentation` `set_sha256`) | `blla` `89aabd48…` / `d3f9fb81…`; `-d horizontal-rl` `83bc6671…` / `a05a34f2…`; Tesseract lines `346f4156…` / `314e7bd0…`; legacy `5462f064…` / `45f0a3df…` (seed-101 / held-out) |

Limits: the R3b limits apply. In addition, one seed per batch, synthetic pages only, and no confidence intervals. The legacy baseline and the anchor and position rules in (b) and (c) are heuristics. Predictions, line files and reports stay local.

## R4c (partial): first trained segmenter, line geometry only (2026-11-03)

R4c trained HeOCR's first baseline segmenter (`heocr-engine train-kraken-seg`, decision 0008) and was **stopped by the team lead after 2 of a planned 15–25 epochs**. R4a showed that a better segmenter alone is capped near 0.22–0.28 CER with R3b (step (e) above), so the training slot went to the recognizer retrain first. No training-run record was written, because the run did not finish. These numbers describe a partially trained model and are not an R4 result. There is no hocrgen text score here; the table is line geometry only.

### Line geometry (`diagnose-segmentation`, polygon IoU ≥ 0.5)

Both rows use `kraken segment -bl -d horizontal-rl`, and only the segmentation model differs. The `blla` rows are R4a's `-d horizontal-rl` line files, rescored with the same tool code (identical to R4a's reports).

| Segmenter | Batch | P / R / F1 | Split gold lines | Merging predicted lines (gold lines merged) | Missed | Spurious | Kendall τ | Adjacent pairs kept | Pages fully in order |
|---|---|---|---|---|---|---|---|---|---|
| `blla -d horizontal-rl` | seed-101 | 0.733 / 0.800 / 0.765 | 78 | 16 (32) | 27 | 1 | 0.838 | 0.866 | 26 / 80 |
| R4c epoch 1 `-d horizontal-rl` | seed-101 | 0.926 / 0.897 / 0.911 | 14 | 27 (54) | 5 | 0 | 0.860 | 0.862 | 13 / 80 |
| `blla -d horizontal-rl` | held-out | 0.624 / 0.726 / 0.671 | 96 | 4 (8) | 28 | 0 | 0.811 | 0.858 | 31 / 80 |
| R4c epoch 1 `-d horizontal-rl` | held-out | 0.912 / 0.886 / 0.899 | 5 | 5 (10) | 20 | 2 | 0.872 | 0.863 | 14 / 80 |

With baseline matching (`--match baseline`), F1 goes from 0.842 to 0.949 on seed-101 and from 0.773 to 0.951 on held-out.

- **Line finding:** after only two epochs, the trained segmenter finds lines much better than `blla`. Splits almost disappear (78 → 14 and 96 → 5 gold lines). On the handwriting-style templates, held-out polygon F1 is 0.979 and 0.934, against 0.767 and 0.691 for `blla`.
- **Merges are stamps:** on seed-101, 27 of the 40 stamp lines are merged with the body line they overlap. Training regions were line bounding boxes. The sidecar's region polygons (R4b1) and a longer run are the obvious next steps.
- **Order:** Kendall τ is slightly better, but fewer pages are perfectly in order. This is not diagnosed yet.
- **Limits:** a partial model (epoch 1, `val_mean_iu` 0.761), one seed, synthetic pages only, and the same generator and fonts as the training batch.

### Run identities

| Part | Identity |
|---|---|
| heocr-engine | training `2add9ed` (R4b); diagnostic `2d8c58c` |
| Training data | `train_batch_s5101` (hocrsyngen `bbcaf0e`): annotations `5d1155cf…`, manifest `29dffcca…`. Split as R3b (by sample, split seed 0, validation fraction 0.05): 1,710 / 90 pages. Regions are `line_polygon_bbox` |
| Training | ketos 7.0.2 `segtrain` from scratch, default network, lr 0.0002, AdamW, constant schedule, no augmentation, `quit early` with lag 8 and min-epochs 10, mps, seed 42. About 24 min/epoch on a shared machine. Stopped during epoch 3 |
| Validation (ketos) | epoch 0: `val_mean_iu` 0.620, baseline F1 0.982; epoch 1: 0.761, baseline F1 0.956 |
| Model | `checkpoint_01-0.7613.ckpt` (sha256 `4b217c7e09913c2d…`) through `ketos convert` gives `3bd77f587eb3abf6…` (safetensors, `topline` false). Licence `Needs verification`, not published (decision 0008) |
| Line-file sets (`set_sha256`) | `46cf7f09…` (seed-101), `9635e25a…` (held-out) |
| Batches | as R4a |


## R3c: recognizer retrained on Kraken-made line polygons (2026-11-03)

R4a found that R3b reads only line polygons shaped like hocrsyngen's own and fails on the polygons Kraken builds at inference (step (e) above). R3c is R3b's recipe with one change: training lines get polygons rebuilt from the gold baselines by Kraken's own polygonizer at the inference height (`train-kraken --line-polygons kraken --polygonizer-height 1800`, PR #13). Data, split and settings are R3b's. The weights are not in this repository and are not published; their licence is `Needs verification` (decision 0007).

Kinds are as in R4a: *diagnostic* rows use gold line geometry or gold order and bound what a fix could gain; *pipeline* rows are real pipelines. Scores are hocrgen `evaluate-references` `primary.v1` on synthetic gold only (decision 0004).

### Seed-101 (S10c gold) and held-out batches (`primary.v1` CER / WER, overall)

| Lines | Kind | R3b seed-101 | R3c seed-101 | R3b held-out | R3c held-out |
|---|---|---|---|---|---|
| `blla -d horizontal-rl` | pipeline | 0.255 / 0.529 | 0.168 / 0.300 | 0.358 / 0.654 | 0.241 / 0.415 |
| `blla`, official `heocr-engine kraken` (default `-d horizontal-rl`) | pipeline | | 0.168 / 0.300 | | 0.241 / 0.415 |
| R4c-e01 segmenter `-d horizontal-rl` (preview) | pipeline, preview | 0.176 / 0.405 | **0.096 / 0.172** | 0.236 / 0.513 | **0.143 / 0.295** |
| Tesseract `--psm 3` lines | pipeline | 0.211 / 0.383 | 0.183 / 0.323 | 0.162 / 0.311 | 0.211 / 0.375 |
| (e) gold baselines, Kraken polygons at height 1800, gold order | diagnostic | 0.193 / 0.451 | 0.018 / 0.044 | 0.250 / 0.538 | 0.006 / 0.021 |
| (d) gold lines with hocrsyngen's polygons, gold order | diagnostic | 0.013 / 0.036 | 0.041 / 0.129 | 0.008 / 0.023 | 0.045 / 0.148 |

Tesseract alone scores 0.338 / 0.553 (seed-101) and 0.353 / 0.535 (held-out).

- **`blla -d horizontal-rl`:** `kraken segment -bl -d horizontal-rl` lines are recognized with `-f page ocr --reorder --base-dir R`. Re-recognizing saved `blla` PAGE output this way matches `segment … ocr` end to end on 2,325 of 2,329 lines (the mixed-script batch below, R3b).
- **Official `heocr-engine kraken`:** the same `blla` pipeline through the engine's runtime (`--base-dir R`, which defaults to `-d horizontal-rl`; decision 0009). Each prediction record names its own segmenter and recognizer. It agrees with the `-f page` row page by page: 2,430 against 2,429 character edits on seed-101 and 2,424 against 2,424 on held-out (E2c6: 0 / 79 / 1 and 1 / 78 / 1 pages improved / unchanged / worsened).
- **R4c-e01 (preview):** the epoch-1 checkpoint of the paused R4c segmenter run (section above, `3bd77f587eb3abf6…`), through `heocr-engine kraken --segmentation-model`. It is a partially trained model, so these rows preview what a trained segmenter can do and are not an R4 result.
- **Tesseract lines:** as in R4a.
- **(e):** the R3c data path's polygonizer, run on the gold baselines. It drops one seed-101 line, which scores as deleted.

**By template, pipelines only (`primary.v1` CER / WER; best CER per row in bold):**

| Template | Tesseract alone | R3b + Tesseract lines | R3c + Tesseract lines | R3c + `blla -d horizontal-rl` | R3c + R4c-e01 (preview) |
|---|---|---|---|---|---|
| **Seed-101, S10c gold** | | | | | |
| `printed_letter` | 0.111 / 0.232 | 0.220 / 0.339 | 0.264 / 0.433 | 0.160 / 0.286 | **0.107** / 0.211 |
| `printed_letter_heavy_scan` | 0.122 / 0.230 | 0.293 / 0.489 | 0.249 / 0.400 | 0.209 / 0.354 | **0.097** / 0.192 |
| `handwritten_note` | 0.641 / 0.998 | 0.111 / 0.266 | **0.071** / 0.170 | 0.147 / 0.272 | 0.090 / 0.137 |
| `handwritten_note_heavy_wear` | 0.658 / 0.994 | 0.181 / 0.412 | 0.089 / 0.218 | 0.143 / 0.273 | **0.085** / 0.128 |
| overall | 0.338 / 0.553 | 0.211 / 0.383 | 0.183 / 0.323 | 0.168 / 0.300 | **0.096** / 0.172 |
| **Held-out s6101** | | | | | |
| `printed_letter` | **0.102** / 0.189 | 0.168 / 0.317 | 0.268 / 0.464 | 0.244 / 0.432 | 0.153 / 0.360 |
| `printed_letter_heavy_scan` | **0.138** / 0.218 | 0.212 / 0.383 | 0.280 / 0.455 | 0.284 / 0.484 | 0.148 / 0.319 |
| `handwritten_note` | 0.687 / 0.976 | **0.095** / 0.186 | 0.133 / 0.249 | 0.210 / 0.360 | 0.139 / 0.239 |
| `handwritten_note_heavy_wear` | 0.663 / 0.976 | 0.149 / 0.327 | **0.117** / 0.272 | 0.207 / 0.356 | 0.128 / 0.232 |
| overall | 0.353 / 0.535 | 0.162 / 0.311 | 0.211 / 0.375 | 0.241 / 0.415 | **0.143** / 0.295 |

**Best pipeline:**
- **Overall, by batch:** R3c + the R4c-e01 preview segmenter is best on both batches, 0.096 (seed-101) and 0.143 (held-out). Without the preview segmenter, the best is R3c + `blla -d horizontal-rl` on seed-101 (0.168) and R3b + Tesseract lines on held-out (0.162).
- **By template:** no pipeline wins everywhere.
  - Tesseract alone wins both printed templates on held-out.
  - R3c + R4c-e01 wins both printed templates on seed-101 (0.107 against 0.111, and 0.097 against 0.122) and seed-101 `handwritten_note_heavy_wear`.
  - A Kraken recognizer on Tesseract's lines wins the other three handwriting-style rows: R3c twice and R3b once (held-out `handwritten_note`).
  - R3c + `blla` wins no single template.
- **Why the overall winners win:** R3c + R4c-e01, and on seed-101 R3c + `blla`, are never far behind on any template. Every other pipeline loses one template family badly.

**Paired accounting (hocrgen E2c6, R3c against R3b, the same lines; pages are items, `primary.v1`):**

| Lines | Batch | Pages improved / unchanged / worsened | Character edits R3b → R3c (removed on improved pages, added on worsened) | Word edits R3b → R3c |
|---|---|---|---|---|
| `blla -d horizontal-rl` | seed-101 | 80 / 0 / 0 | 3,679 → 2,429 (−1,250, +0) | 1,337 → 758 |
| `blla -d horizontal-rl` | held-out | 79 / 1 / 0 | 3,603 → 2,424 (−1,179, +0) | 1,221 → 774 |
| Tesseract lines | seed-101 | 48 / 4 / 28 | 3,042 → 2,643 (−764, +365) | 968 → 816 |
| Tesseract lines | held-out | 22 / 1 / 57 | 1,630 → 2,129 (−203, +702) | 581 → 699 |
| (e) | seed-101 | 80 / 0 / 0 | 2,782 → 264 (−2,518, +0) | 1,139 → 111 |
| (e) | held-out | 80 / 0 / 0 | 2,514 → 59 (−2,455, +0) | 1,004 → 40 |
| (d) | seed-101 | 5 / 6 / 69 | 184 → 589 (−7, +412) | 92 → 325 |
| (d) | held-out | 8 / 13 / 59 | 80 → 455 (−18, +393) | 43 → 276 |

Segmenter swaps and comparisons with Tesseract alone (E2c6, pages improved / unchanged / worsened, character edits baseline → candidate):

| Candidate against baseline | Seed-101 | Held-out |
|---|---|---|
| R3c against R3b, both on R4c-e01 lines | 75 / 0 / 5, 2,536 → 1,385 | 75 / 0 / 5, 2,373 → 1,444 |
| R4c-e01 against `blla -d horizontal-rl`, both R3c | 71 / 4 / 5, 2,430 → 1,385 | 74 / 2 / 4, 2,424 → 1,444 |
| R3c + `blla -d horizontal-rl` against Tesseract alone | 43 / 1 / 36, 4,877 → 2,430 | 44 / 0 / 36, 3,558 → 2,424 |
| R3c + R4c-e01 against Tesseract alone | 61 / 3 / 16, 4,877 → 1,385 | 52 / 2 / 26, 3,558 → 1,444 |

The counts are per-page differences in edit distance, not aligned individual errors. They come from hocrgen `main` (`c8fb74e`, E2c6). Its `scored` block is identical to `2d3efb0`'s on all 25 earlier R3/R4a sets, so the CER above is the same under either version.

**Matched lines (raw NFC line CER on lines matched one-to-one, polygon IoU ≥ 0.5):**

| Lines | Recognizer | Seed-101 predicted crops / (e) crops | Held-out predicted crops / (e) crops |
|---|---|---|---|
| `blla -d horizontal-rl` (512 / 467 lines) | R3b | 0.211 / 0.189 | 0.267 / 0.266 |
| `blla -d horizontal-rl` | R3c | 0.091 / 0.016 | 0.098 / 0.006 |
| Tesseract lines (440 / 468 lines) | R3b | 0.109 / 0.160 | 0.081 / 0.231 |
| Tesseract lines | R3c | 0.107 / 0.016 | 0.152 / 0.005 |

### Mixed-script batch (hocrgen evaluation fixture)

The project's target documents mix Hebrew with Latin and digits, but the training text is about 0.5% Latin (382 of 9,359 corpus lines). This batch is hocrgen's [mixed-script synthetic recipe](https://github.com/HeOCR/hocrgen/blob/main/docs/evaluation-fixtures/bidi-synthetic-recipe.md):
- 100 pages, 25 each of `printed_letter`, `handwritten_note`, `archive_card` and `ledger`, with text that mixes Hebrew with Latin names and digits;
- a seed and text holdout only, since templates and fonts are the training generator's;
- an evaluation fixture: nothing is trained on it.

It reproduces exactly from the recipe:
- manifest and line-annotation sha256 equal the recorded ones, and all 100 image hashes match;
- the Tesseract binary and models match the recipe;
- re-running Tesseract `heb+eng` gives the recorded 15,780 / 27,443 character edits, with every family identical.

`primary.v1` CER per family (hocrgen `c8fb74e`, whose source is the recipe's `9aff7d4`):

| Lines | Kind | Recognizer | `printed_letter` | `handwritten_note` | `archive_card` | `ledger` | overall CER / WER |
|---|---|---|---|---|---|---|---|
| Tesseract `heb+eng` alone (recipe baseline) | pipeline | Tesseract | 0.177 | 0.737 | 0.444 | 0.770 | 0.575 / 0.723 |
| `blla -d horizontal-rl` | pipeline | R3b | 0.348 | 0.345 | 0.452 | 0.746 | 0.543 / 0.784 |
| `blla -d horizontal-rl` | pipeline | R3c | 0.243 | 0.260 | 0.386 | 0.676 | **0.465 / 0.650** |
| Tesseract `heb` lines | pipeline | R3b | 0.291 | 0.278 | 0.520 | 0.787 | 0.553 / 0.741 |
| Tesseract `heb` lines | pipeline | R3c | 0.313 | 0.238 | 0.583 | 0.839 | 0.588 / 0.775 |
| `blla` lines in gold order | diagnostic | R3c | 0.194 | 0.206 | 0.115 | 0.310 | 0.230 / 0.443 |
| (e) at height 1800 | diagnostic | R3b | 0.323 | 0.277 | 0.322 | 0.481 | 0.385 / 0.648 |
| (e) at height 1800 | diagnostic | R3c | 0.122 | 0.144 | 0.077 | 0.285 | 0.188 / 0.306 |

On this batch the polygonizer drops 2 of 2,305 gold lines (geometry errors), which score as deleted.

**By script.** The left three columns project each page's reference and prediction onto one character class (Latin letters, ASCII digits or Hebrew letters) and score the edit distance of the projections. This measures whether a class was read, not where it was placed, and a rate can pass 1 when a system adds characters of that class. The right two columns give raw line CER on matched lines, split by whether the gold line contains Latin.

| Lines | Recognizer | Latin letters (1,795) | Digits (5,119) | Hebrew letters (11,958) | Lines with Latin | Pure Hebrew lines |
|---|---|---|---|---|---|---|
| Tesseract `heb+eng` alone | Tesseract | 0.892 | 0.668 | 0.381 | | |
| `blla -d horizontal-rl` | R3b | 0.910 | 0.640 | 0.421 | 0.340 (319 / 339) | 0.287 (1,808 / 1,966) |
| `blla -d horizontal-rl` | R3c | 0.798 | 0.590 | 0.203 | 0.233 (319 / 339) | 0.055 (1,808 / 1,966) |
| (e) | R3b | 0.919 | 0.351 | 0.354 | 0.334 | 0.317 |
| (e) | R3c | **0.787** | 0.079 | 0.033 | **0.190** | **0.004** |

**Line geometry (`diagnose-segmentation`, polygon IoU ≥ 0.5, 2,305 gold lines):**
- **`blla -d horizontal-rl`:** P / R / F1 0.913 / 0.923 / 0.918, Kendall τ 0.565, adjacent pairs kept 0.449. τ by family: `archive_card` 0.464, `ledger` 0.562, `printed_letter` 0.816, `handwritten_note` 0.916.
- **Tesseract `heb` lines:** 0.737 / 0.604 / 0.664. It merges ledger cells: 412 predicted lines cover 841 gold lines.

**Paired accounting (E2c6, pages):**
- R3c against R3b, `blla -d horizontal-rl`: 99 pages improved, 1 unchanged, 0 worsened (14,915 → 12,748 character edits).
- R3c against R3b, (e): 100 / 0 / 0 (10,576 → 5,151).
- R3c against R3b, Tesseract lines: 26 / 2 / 72 (15,188 → 16,129).
- R3c + `blla -d horizontal-rl` against Tesseract alone: 71 pages improved, 0 unchanged, 29 worsened (15,780 → 12,748; −3,675 on improved pages, +643 on worsened).

### Reading

- **R3c fixes the crop mismatch R4a found.** On Kraken's polygons around the true baselines, CER falls from 0.193 / 0.250 to 0.018 / 0.006, and every page improves. That is near R3b's own oracle level (0.013 / 0.008).
- **End to end with `blla -d horizontal-rl`, R3c is better than R3b on all but one page** of both batches (159 of 160 pages; none is worse): 0.168 against 0.255 on seed-101 and 0.241 against 0.358 on held-out.
  - It is now better than Tesseract alone overall on both batches (0.338 and 0.353), but not per template.
  - It is still clearly worse than Tesseract on every printed template, for example 0.244 against 0.102 on held-out `printed_letter`.
  - See "Best pipeline" above for the per-batch and per-template winners.
- **R3c is specialised to Kraken's polygons.**
  - On hocrsyngen's own polygons (d) it is worse than R3b on both batches.
  - On Tesseract's rectangles it is worse on held-out (0.211 against 0.162) and on the mixed-script batch, but better on seed-101 (0.183 against 0.211).
  - The held-out paired counts show the split: 22 pages improved and 57 worsened.
  - Mixing crop styles in training (both polygon sources, or rectangles as augmentation) is the obvious next experiment.
- **A trained segmenter is now the larger lever, and the two fixes compound.**
  - R4c-e01, only two epochs into a paused run, takes R3c from 0.168 to 0.096 and from 0.241 to 0.143. It improves 71 and 74 of 80 pages and worsens 5 and 4.
  - With R3b, the same segmenter gets only to 0.176 and 0.236: R3b still cannot read Kraken's polygons, whatever the baselines.
  - Finishing R4c (or R4d) and re-scoring it with R3c (or R3d) is the obvious next step.
- **The remaining `blla` gap is segmentation again.** Between `blla` lines (0.168 / 0.241) and (e) (0.018 / 0.006) lie reading order, line finding, and crops built around `blla`'s rather than the true baselines (matched-line CER 0.091 / 0.098 against 0.016 / 0.006).
- **Mixed script: R3c cannot read Latin.** Even with every true baseline, it gets 79% of Latin letters wrong. Pure Hebrew lines read almost perfectly (0.004) and lines containing Latin have CER 0.190. Digits are fine (0.079). This is a training-text gap, not a geometry problem: the corpus has almost no Latin.
- **Mixed script: reading order costs most end to end.** On `archive_card` and `ledger`, `blla`'s order is poor (τ 0.46 and 0.56). Putting R3c's `blla` lines into gold order alone takes CER from 0.465 to 0.230 (`ledger` 0.676 → 0.310, `archive_card` 0.386 → 0.115).
- **Tesseract lines do not help** the mixed-script batch: Tesseract joins ledger cells into rows.

### Run identities

| Part | Identity |
|---|---|
| heocr-engine | training and the official `heocr-engine kraken` rows `cade9c8` (R3c data path, PR #13); diagnostics and conversion `aa67fa7` |
| Training | R3b's batch (`train_batch_s5101`), split and ketos settings (table above), plus `--line-polygons kraken --polygonizer-height 1800`. `data.polygonizer`: `kraken.lib.segmentation.calculate_polygonal_environment`, Kraken 7.0.2, height 1800, `topline` false, boundaries "other baselines", 0 lines dropped. Train 1,710 pages / 27,487 lines, validation 90 / 1,553. mps, seed 42, not deterministic |
| Training outcome | Early stopping after 10 epochs; best epoch 6 (0-based), val_accuracy 0.9976 (kraken-internal, display order). History 0.9689, 0.9911, 0.9949, 0.9955, 0.9958, 0.9967, 0.9976, 0.9973, 0.9969, 0.9970 |
| Model | `best_0.9976.safetensors`, sha256 `db4807d1503bfec0295ee9dad501c2ac1d2192077644ac3a6e045a7cf6400afd`, 16,138,352 bytes; licence `Needs verification`, unpublished |
| Inference | Kraken 7.0.2 on cpu, `blla` `77a638a83c9e5356…`; Tesseract 5.5.3 as in R4a (`heb` lines; `heb+eng` for the recipe baseline, `eng` `7d4322bd2a774972…`) |
| hocrgen | `2d3efb0` for the seed-101 and held-out CER; `c8fb74e` (main, E2c6; source identical to `9aff7d4`) for paired accounting and the mixed-script batch |
| Seed-101 and held-out | as R4a |
| Mixed-script batch | hocrsyngen `bc4394c` (S11b), Python 3.12.11, Pillow 12.2.0, raqm 0.10.3, FreeType 2.14.3. Recipe seed 26110302, corpus `b325673476bce8c1…`. Manifest `5979ada50f085e91e6f2d43f9286daea3c4fe4acb0718bf5dfb1962b31b4cdbe`, line annotations `5a6ba66ca8cba5a1a6071b95a0a7774e698f2c713dc304a48ed3b1f3e0994d3f` |
| Official `heocr-engine kraken` sets (records name their own models) | Seed-101: R3c + `blla` `2af3d834d311a6d0…`, R3c + R4c-e01 `c7a4851e6bb14042…`, R3b + R4c-e01 `0516c8a19e08fa0d…`. Held-out: `5d63089e848fe5a4…`, `789179a7d8788327…`, `9b6aecedf28b09c9…` |
| R4c-e01 segmenter (preview) | `checkpoint_01-0.7613.ckpt` converted to safetensors `3bd77f587eb3abf6…` (R4c section above); licence `Needs verification`, unpublished |
| R3c prediction sets, seed-101 | `blla -d horizontal-rl` `075aceecce972bd1…`, Tesseract lines `d4a3e1c7ed973b93…`, (e) `6c837d721d2b95a4…`, (d) `9015d0804c3667f5…` |
| R3c prediction sets, held-out | `blla -d horizontal-rl` `a6eea35ce7eafe71…`, Tesseract lines `05fa40836f3cf6ff…`, (e) `78ee1e8c01115109…`, (d) `3ab26518d3d673ae…` |
| Mixed-script prediction sets | Tesseract `heb+eng` `56186fa22774f2a8…`; R3b: `blla` `fd9fd89609818622…`, Tesseract lines `6a1ec8f99efbcf1e…`, (e) `c1f352f3384bab7b…`; R3c: `blla` `7fef60e5e3c1d597…`, Tesseract lines `9a3d673e5aa07d83…`, `blla` in gold order `1974773866da03b4…`, (e) `46e28acf7485a5d7…` |
| Line-file sets (mixed) | `blla -d horizontal-rl` `196354a8100c088a…`, Tesseract lines `82a35d2a88bc81e5…` |

Limits: the R3b and R4a limits apply. One training run, one seed per batch, and no confidence intervals. The mixed-script batch shares the training generator's templates and fonts, and its 100 corpus lines are built from ten prefixes and ten endings. The script projection is a diagnostic, not a hocrgen profile. Predictions, line files and reports stay local.
