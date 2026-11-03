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
- **Line order:** segmentation runs with `-d horizontal-rl` by default (`--text-direction`, or `"text_direction"` in a pipeline config), so lines that share a row are read right to left. `--text-direction horizontal-lr` restores Kraken's own default. The direction is in the stage `details` and in its `config_sha256`. **R2a and R3b predictions predate this option and used `horizontal-lr`**; their stage details have no `text_direction`. In R4a, `horizontal-rl` lowered R3b + `blla` overall CER from 0.286 to 0.255 (seed-101) and from 0.405 to 0.358 (held-out).
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
