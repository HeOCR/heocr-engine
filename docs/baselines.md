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
- **Python API, opt-in (`--api python`, R4d2):** runs the same Kraken segmentation and recognition in-process (needs the `kraken` extra; no `--executable`), so that it can apply a learned line reading order and write geometry. The CLI path above stays the default, and without a reading-order model the text follows the same heuristic line order.

  ```sh
  heocr-engine kraken page.png prediction.json --api python \
    --segmentation-model seg.safetensors --recognition-model rec.safetensors \
    --reading-order-model ro.safetensors --geometry-output geometry.json
  ```

  - `--reading-order-model` takes a line-level (`baselines`) model from `ketos rotrain`. A reading-order model is used only when this flag names a file, never picked up implicitly from the segmentation file. The file may be the segmentation file itself when that is a `ketos convert` combination of both models (R4d). Its line types must match the segmentation model's. The text then follows the learned order.
  - **Why the order is recomputed here:** Kraken 7.0.2 does not deliver a usable learned order. `kraken … ocr` writes plain text in the heuristic order even when a reading-order model is attached. The deprecated `blla.segment` stores the learned order in `line_orders` as indices into its line list *before* the heuristic sort, next to the sorted lines, so reading the returned lines by those indices gives the heuristic order back. `tests/test_kraken_api.py` (`KrakenLineOrdersBugTests`) proves this against Kraken's own code. The stage keeps the pre-sort list Kraken hands its heuristic order function, runs the reading-order model on that list, and maps the result onto the returned lines by line id. It fails closed unless the result is a permutation. Not reported upstream yet; that needs the maintainer's go-ahead.
  - The stage is named `kraken-python`. Its artifacts are `library:kraken-record` (sha256 of the installed Kraken distribution's `RECORD` file list), `model:segmentation`, `model:recognition` and, with a learned order, `model:reading-order`. `details` has `api: "python"`, `neural_reading_order` (true with a reading-order model), `line_order` (`learned` or `heuristic`), `reading_order_model_sha256`, `lines`, `lines_moved_by_learned_order` and `region_counts` per predicted region type.
  - `--geometry-output` writes `heocr_engine_kraken_geometry.v1`: the input sha256, `unit: "pixel"`, and per line its order, heuristic order, Kraken line type, region ids, baseline, polygon, `[x, y, width, height]` box and text, plus the predicted typed regions (for example `table_cells`) with polygons and boxes. Points are clamped to the image, and `clipped` marks any that were moved. Predicted regions are the segmenter's own detections, not generator gold. This is not the `heocr_engine.bidi` geometry contract (no word boxes); an adapter to it is future work.
  - `--reading-order-classes region` (R4e, opt-in; pipeline key `reading_order_classes`) changes what the reading-order model sees as each line's class. The default, `segmenter`, is the segmenter's line types, and its config digest is unchanged. In region mode each line is tagged with a predicted region type, and the reading-order model's own class mapping is used:
    1. `stamp_area` if the segmenter typed the line `stamp`, because a stamp also lies in the body region under it;
    2. otherwise the type of the first region Kraken lists for the line;
    3. otherwise `default`.

    Kraken's line features are position plus class, so a model that only sees line types cannot learn a label column beside body text (R4e). The model must be trained on region-typed lines (`prepare-kraken-data --task segmentation --line-type REGION=REGION` for each region). The stage fails closed:
    - if the model's classes are line types or empty;
    - if they include a region type the segmenter never predicts;
    - if the segmenter types `stamp` lines and the model has no `stamp_area` class.

    `details` adds `reading_order_classes` and `reading_order_class_counts`.
  - `diagnose-segmentation` reads these geometry files directly when they are named `<page_sha256>.json`, and scores the learned order without a PAGE conversion.
  - The stage fails closed unless Kraken returns exactly one recognition record per segmented line.
  - `--device` is `cpu` (default), `mps` or `cuda`. In a pipeline config: `{"type": "kraken-python", "segmentation_model": "…", "recognition_model": "…", "reading_order_model": "…", "base_dir": "R"}`.
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
- **Order:** Kendall τ is slightly better, but fewer pages are perfectly in order. The cause is Kraken's heuristic line order, not the trained segmenter. With `-d horizontal-rl`, the column rule in `polygonal_reading_order` treats the short footer at the right edge as a right-hand column, because it has no x-overlap with the signature row or the margin notes. So the footer is read first, and the signature and margin lines after it. That is the dominant discordant pair for both segmenters (`diagnose-segmentation --lines`, against gold line order):

  | Discordant pair | `blla` seed-101 | R4c seed-101 | `blla` held-out | R4c held-out |
  |---|---|---|---|---|
  | `signature_area` read after `footer` | 87 | 95 | 84 | 81 |
  | margin read after `footer` | 21 | 31 | 17 | 32 |

  R4c loses fully-ordered pages mainly because it *finds* more margin lines (seed-101: 34 matched, against 24 for `blla`), and each of them is then misplaced against the footer. Typed regions do not fix this, because the footer region is still a small box on the right. R4d's learned reading order does (below).
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

## R3d: recognizer trained on mixed Hebrew/Latin text (2026-11-03)

R3c cannot read Latin (section above), because its training text is about 0.5% Latin. R3d keeps R3c's recipe (Kraken polygons at height 1800, settings, from scratch) and changes the training batch:
- **Text:** the S10b Hebrew train corpus (9,359 lines) followed by the S13a mixed Hebrew/Latin train corpus (5,810 lines), 15,169 lines in all.
- **Templates:** seven, the four benchmark templates plus `archive_card`, `archive_card_faded_scan` and `ledger`. R3b and R3c saw only the four benchmark templates.
- **Size:** 2,400 pages, seed 7101.

Neither evaluation batch below is trained on. The weights are not in this repository and are not published; their licence is `Needs verification` (decision 0007). Kinds and scoring are as in the R3c section.

### Seed-101 (S10c gold) and held-out batches (`primary.v1` CER / WER, overall)

| Lines | Kind | R3b seed-101 | R3c seed-101 | R3d seed-101 | R3b held-out | R3c held-out | R3d held-out |
|---|---|---|---|---|---|---|---|
| `blla -d horizontal-rl` | pipeline | 0.255 / 0.529 | 0.168 / 0.300 | **0.167 / 0.292** | 0.358 / 0.654 | 0.241 / 0.415 | **0.240 / 0.405** |
| Tesseract `--psm 3` lines | pipeline | 0.211 / 0.383 | **0.183 / 0.323** | 0.194 / 0.356 | **0.162 / 0.311** | 0.211 / 0.375 | 0.196 / 0.362 |
| (e) gold baselines, Kraken polygons at height 1800, gold order | diagnostic | 0.193 / 0.451 | 0.018 / 0.044 | **0.018 / 0.040** | 0.250 / 0.538 | 0.006 / 0.021 | **0.006 / 0.020** |
| (d) gold lines with hocrsyngen's polygons, gold order | diagnostic | **0.013 / 0.036** | 0.041 / 0.129 | 0.028 / 0.096 | **0.008 / 0.023** | 0.045 / 0.148 | 0.024 / 0.106 |

Tesseract alone scores 0.338 / 0.553 (seed-101) and 0.353 / 0.535 (held-out). R3d was not run on the R4c-e01 preview segmenter; the R3c + R4c-e01 rows above stay the best seed-101 and held-out pipelines.

**By template, pipelines only (`primary.v1` CER / WER; best CER per row in bold):**

| Template | Tesseract alone | R3b + Tesseract lines | R3c + Tesseract lines | R3d + Tesseract lines | R3c + `blla -d horizontal-rl` | R3d + `blla -d horizontal-rl` | R3c + R4c-e01 (preview) |
|---|---|---|---|---|---|---|---|
| **Seed-101, S10c gold** | | | | | | | |
| `printed_letter` | 0.111 / 0.232 | 0.220 / 0.339 | 0.264 / 0.433 | 0.282 / 0.491 | 0.160 / 0.286 | 0.159 / 0.283 | **0.107** / 0.211 |
| `printed_letter_heavy_scan` | 0.122 / 0.230 | 0.293 / 0.489 | 0.249 / 0.400 | 0.258 / 0.417 | 0.209 / 0.354 | 0.204 / 0.351 | **0.097** / 0.192 |
| `handwritten_note` | 0.641 / 0.998 | 0.111 / 0.266 | **0.071** / 0.170 | 0.080 / 0.200 | 0.147 / 0.272 | 0.148 / 0.258 | 0.090 / 0.137 |
| `handwritten_note_heavy_wear` | 0.658 / 0.994 | 0.181 / 0.412 | 0.089 / 0.218 | 0.096 / 0.241 | 0.143 / 0.273 | 0.144 / 0.256 | **0.085** / 0.128 |
| overall | 0.338 / 0.553 | 0.211 / 0.383 | 0.183 / 0.323 | 0.194 / 0.356 | 0.168 / 0.300 | 0.167 / 0.292 | **0.096** / 0.172 |
| **Held-out s6101** | | | | | | | |
| `printed_letter` | **0.102** / 0.189 | 0.168 / 0.317 | 0.268 / 0.464 | 0.252 / 0.458 | 0.244 / 0.432 | 0.241 / 0.417 | 0.153 / 0.360 |
| `printed_letter_heavy_scan` | **0.138** / 0.218 | 0.212 / 0.383 | 0.280 / 0.455 | 0.267 / 0.448 | 0.284 / 0.484 | 0.283 / 0.472 | 0.148 / 0.319 |
| `handwritten_note` | 0.687 / 0.976 | **0.095** / 0.186 | 0.133 / 0.249 | 0.123 / 0.239 | 0.210 / 0.360 | 0.210 / 0.352 | 0.139 / 0.239 |
| `handwritten_note_heavy_wear` | 0.663 / 0.976 | 0.149 / 0.327 | 0.117 / 0.272 | **0.097** / 0.241 | 0.207 / 0.356 | 0.209 / 0.351 | 0.128 / 0.232 |
| overall | 0.353 / 0.535 | 0.162 / 0.311 | 0.211 / 0.375 | 0.196 / 0.362 | 0.241 / 0.415 | 0.240 / 0.405 | **0.143** / 0.295 |

**Paired accounting (E2c6, R3d against R3c, the same lines; pages improved / unchanged / worsened, character edits R3c → R3d):**

| Lines | Seed-101 | Held-out |
|---|---|---|
| `blla -d horizontal-rl` | 37 / 19 / 24, 2,429 → 2,406 | 26 / 29 / 25, 2,424 → 2,415 |
| Tesseract lines | 23 / 8 / 49, 2,643 → 2,805 | 48 / 7 / 25, 2,129 → 1,976 |
| (e) | 23 / 34 / 23, 264 → 259 | 17 / 52 / 11, 59 → 58 |
| (d) | 48 / 15 / 17, 589 → 402 | 48 / 14 / 18, 455 → 243 |

### Mixed-script batches

Two batches mix Hebrew with Latin names and digits:
- **hocrgen's mixed-script fixture**, the 100-page batch from the R3c section. Templates as above (`printed_letter`, `handwritten_note`, `archive_card`, `ledger`). None of its 100 text lines is in R3d's training text, and only 2 of its 12 Latin words are ("A" and "B"). It tests unseen Latin words, but `archive_card` and `ledger` are now training templates.
- **eval-mixed-heldout**, 80 pages from hocrsyngen's packaged mixed-script eval corpus (`hebrew_mixed_lines_eval_v1.txt`), seed 8101, 20 each of the four benchmark templates. It is held out and never trained on. None of its 401 text lines is in R3d's training text, but 153 of its 218 Latin words (two letters or more) are. Its templates are the four that R3b and R3c also trained on, so it isolates the change of training text.

Both are scored on synthetic gold only (decision 0004).

**hocrgen fixture, `primary.v1` CER per family** (hocrgen `c8fb74e`, as in the R3c section):

| Lines | Kind | Recognizer | `printed_letter` | `handwritten_note` | `archive_card` | `ledger` | overall CER / WER |
|---|---|---|---|---|---|---|---|
| Tesseract `heb+eng` alone (recipe baseline) | pipeline | Tesseract | 0.177 | 0.737 | 0.444 | 0.770 | 0.575 / 0.723 |
| `blla -d horizontal-rl` | pipeline | R3b | 0.348 | 0.345 | 0.452 | 0.746 | 0.543 / 0.784 |
| `blla -d horizontal-rl` | pipeline | R3c | 0.243 | 0.260 | 0.386 | 0.676 | 0.465 / 0.650 |
| `blla -d horizontal-rl` | pipeline | R3d | **0.172** | 0.181 | **0.332** | **0.657** | **0.419 / 0.598** |
| Tesseract `heb` lines | pipeline | R3b | 0.291 | 0.278 | 0.520 | 0.787 | 0.553 / 0.741 |
| Tesseract `heb` lines | pipeline | R3c | 0.313 | 0.238 | 0.583 | 0.839 | 0.588 / 0.775 |
| Tesseract `heb` lines | pipeline | R3d | 0.266 | **0.163** | 0.534 | 0.829 | 0.552 / 0.744 |
| (e) at height 1800 | diagnostic | R3b | 0.323 | 0.277 | 0.322 | 0.481 | 0.385 / 0.648 |
| (e) at height 1800 | diagnostic | R3c | 0.122 | 0.144 | 0.077 | 0.285 | 0.188 / 0.306 |
| (e) at height 1800 | diagnostic | R3d | 0.059 | 0.057 | 0.028 | 0.259 | 0.140 / 0.260 |
| (d) | diagnostic | R3b | 0.132 | 0.180 | 0.092 | 0.288 | 0.199 / 0.312 |
| (d) | diagnostic | R3c | 0.149 | 0.160 | 0.114 | 0.328 | 0.222 / 0.457 |
| (d) | diagnostic | R3d | 0.068 | 0.074 | 0.048 | 0.276 | 0.156 / 0.316 |

Bold marks the best pipeline per column.

Two gold conventions in this fixture charge every line-based system:
- **`ledger` cells.** The gold joins a row's cells with ` | `, but a Kraken pipeline emits one line per cell. Each of the 1,000 separators costs 3 edits, so about 3,000 of R3d's 3,112 `ledger` (e) edits are this convention. Lines matched one to one have `ledger` CER 0.085 (with Latin) and 0.006 (pure Hebrew).
- **Em dashes.** The gold has 325 em dashes (`—`). R3d's training annotations have none, so it writes `-`.

Neither convention occurs in eval-mixed-heldout.

**eval-mixed-heldout, `primary.v1` CER / WER per template** (hocrgen `2d3efb0`; `c8fb74e` gives an identical `scored` block on every R3d set):

| Lines | Kind | Recognizer | `printed_letter` | `printed_letter_heavy_scan` | `handwritten_note` | `handwritten_note_heavy_wear` | overall |
|---|---|---|---|---|---|---|---|
| Tesseract `heb+eng` alone | pipeline | Tesseract | **0.171** / 0.278 | **0.152** / 0.236 | 0.775 / 0.963 | 0.794 / 0.983 | 0.425 / 0.562 |
| `blla -d horizontal-rl` | pipeline | R3b | 0.429 / 0.687 | 0.482 / 0.795 | 0.376 / 0.621 | 0.430 / 0.710 | 0.433 / 0.709 |
| `blla -d horizontal-rl` | pipeline | R3c | 0.331 / 0.524 | 0.298 / 0.473 | 0.264 / 0.384 | 0.288 / 0.448 | 0.298 / 0.463 |
| `blla -d horizontal-rl` | pipeline | R3d | 0.258 / 0.457 | 0.232 / 0.410 | 0.187 / 0.311 | 0.230 / 0.380 | 0.229 / 0.396 |
| Tesseract `heb` lines | pipeline | R3b | 0.254 / 0.419 | 0.277 / 0.417 | 0.208 / 0.311 | 0.158 / 0.297 | 0.231 / 0.369 |
| Tesseract `heb` lines | pipeline | R3c | 0.322 / 0.507 | 0.313 / 0.459 | 0.190 / 0.325 | 0.179 / 0.318 | 0.262 / 0.414 |
| Tesseract `heb` lines | pipeline | R3d | 0.269 / 0.487 | 0.250 / 0.435 | **0.117** / 0.308 | **0.099** / 0.228 | **0.196 / 0.379** |
| (e) at height 1800 | diagnostic | R3b | 0.295 / 0.533 | 0.405 / 0.729 | 0.277 / 0.523 | 0.311 / 0.595 | 0.326 / 0.601 |
| (e) at height 1800 | diagnostic | R3c | 0.085 / 0.100 | 0.079 / 0.097 | 0.099 / 0.127 | 0.089 / 0.125 | 0.087 / 0.110 |
| (e) at height 1800 | diagnostic | R3d | 0.009 / 0.031 | 0.011 / 0.033 | 0.019 / 0.051 | 0.020 / 0.062 | 0.014 / 0.043 |
| (d) | diagnostic | R3b | 0.096 / 0.102 | 0.075 / 0.086 | 0.115 / 0.125 | 0.111 / 0.140 | 0.097 / 0.110 |
| (d) | diagnostic | R3c | 0.133 / 0.306 | 0.175 / 0.303 | 0.111 / 0.156 | 0.105 / 0.185 | 0.134 / 0.247 |
| (d) | diagnostic | R3d | 0.037 / 0.144 | 0.062 / 0.214 | 0.029 / 0.098 | 0.033 / 0.092 | 0.042 / 0.143 |

Bold marks the best pipeline per column. The polygonizer drops no eval-mixed-heldout line.

**By script.** These are the projections from the R3c section: page CER on Latin letters, ASCII digits and Hebrew letters (reference counts in brackets), then raw line CER on lines matched one to one, split by whether the gold line has Latin (matched / gold lines for `blla`).

| Batch | Lines | Recognizer | Latin letters | Digits | Hebrew letters | Lines with Latin | Pure Hebrew lines |
|---|---|---|---|---|---|---|---|
| hocrgen fixture (1,795 / 5,119 / 11,958) | Tesseract `heb+eng` alone | Tesseract | 0.892 | 0.668 | 0.381 | | |
| | `blla -d horizontal-rl` | R3c | 0.798 | 0.590 | 0.203 | 0.233 (319 / 339) | 0.055 (1,808 / 1,966) |
| | `blla -d horizontal-rl` | R3d | **0.060** | 0.541 | 0.176 | 0.107 (319 / 339) | 0.042 (1,808 / 1,966) |
| | Tesseract `heb` lines | R3c | 1.052 | 0.678 | 0.374 | | |
| | Tesseract `heb` lines | R3d | 1.019 | 0.702 | 0.319 | | |
| | (e) | R3c | 0.787 | 0.079 | 0.033 | 0.190 | 0.004 |
| | (e) | R3d | **0.045** | **0.014** | **0.008** | **0.065** | 0.006 |
| | (d) | R3c | 0.833 | 0.163 | 0.053 | 0.204 | 0.101 |
| | (d) | R3d | 0.133 | 0.048 | 0.018 | 0.077 | 0.046 |
| eval-mixed-heldout (873 / 750 / 6,566) | Tesseract `heb+eng` alone | Tesseract | 1.378 | 0.636 | 0.448 | | |
| | `blla -d horizontal-rl` | R3b | 0.934 | 0.675 | 0.424 | | |
| | `blla -d horizontal-rl` | R3c | 0.794 | 0.411 | 0.247 | 0.332 (103 / 117) | 0.089 (368 / 525) |
| | `blla -d horizontal-rl` | R3d | **0.094** | 0.165 | 0.232 | 0.099 (103 / 117) | 0.089 (368 / 525) |
| | Tesseract `heb` lines | R3b | 0.872 | 0.560 | 0.184 | | |
| | Tesseract `heb` lines | R3c | 0.944 | 0.545 | 0.200 | | |
| | Tesseract `heb` lines | R3d | 0.456 | 0.349 | 0.171 | | |
| | (e) | R3b | 0.928 | 0.629 | 0.337 | 0.442 | 0.296 |
| | (e) | R3c | 0.774 | 0.311 | 0.029 | 0.270 | 0.005 |
| | (e) | R3d | **0.039** | **0.033** | **0.002** | **0.033** | 0.005 |
| | (d) | R3b | 0.794 | 0.400 | 0.052 | | |
| | (d) | R3c | 0.810 | 0.329 | 0.073 | 0.276 | 0.077 |
| | (d) | R3d | 0.123 | 0.109 | 0.020 | 0.052 | 0.040 |

The same projection on the Hebrew-only batches (seed-101 has no Latin reference letters; held-out has 28):

| Lines | Seed-101 digits (233) R3b / R3c / R3d | Seed-101 Hebrew letters (11,306) | Held-out digits (397) | Held-out Hebrew letters (7,619) |
|---|---|---|---|---|
| `blla -d horizontal-rl` | 0.712 / 0.352 / 0.292 | 0.247 / 0.144 / 0.144 | 0.539 / 0.234 / 0.247 | 0.366 / 0.224 / 0.225 |
| Tesseract lines | 0.506 / 0.785 / 0.747 | 0.202 / 0.170 / 0.183 | 0.282 / 0.534 / 0.448 | 0.158 / 0.193 / 0.180 |
| (e) | 0.850 / 0.052 / 0.052 | 0.200 / 0.015 / 0.015 | 0.554 / 0.033 / 0.035 | 0.273 / 0.004 / 0.004 |
| (d) | 0.047 / 0.352 / 0.116 | 0.009 / 0.033 / 0.023 | 0.040 / 0.179 / 0.083 | 0.006 / 0.038 / 0.019 |

On Tesseract lines, R3c and R3d write Latin letters that are not on the page: 159 and 237 on seed-101, which has none in its gold, against 1 and 5 on `blla` lines.

**Paired accounting (E2c6, pages improved / unchanged / worsened, character edits baseline → candidate):**

| Candidate against baseline | hocrgen fixture | eval-mixed-heldout |
|---|---|---|
| R3d against R3c, `blla -d horizontal-rl` | 100 / 0 / 0, 12,748 → 11,495 | 62 / 7 / 11, 3,093 → 2,379 |
| R3d against R3c, Tesseract lines | 89 / 1 / 10, 16,129 → 15,161 | 64 / 3 / 13, 2,716 → 2,030 |
| R3d against R3c, (e) | 100 / 0 / 0, 5,151 → 3,837 | 62 / 11 / 7, 907 → 143 |
| R3d against R3c, (d) | 99 / 0 / 1, 6,091 → 4,282 | 71 / 0 / 9, 1,395 → 434 |
| R3d + `blla -d horizontal-rl` against Tesseract alone | 78 / 0 / 22, 15,780 → 11,495 | 52 / 0 / 28, 4,414 → 2,379 |
| R3d + Tesseract lines against Tesseract alone | 29 / 1 / 70, 15,780 → 15,161 | 48 / 0 / 32, 4,414 → 2,030 |

### Best pipeline

- **Seed-101 and held-out:** unchanged from R3c. R3c + R4c-e01 (preview) is best (0.096 and 0.143). Without the preview segmenter, R3d + `blla` is best on seed-101 (0.167, against R3c's 0.168) and R3b + Tesseract lines on held-out (0.162). By template, R3d wins only held-out `handwritten_note_heavy_wear` (R3d + Tesseract lines, 0.097).
- **hocrgen fixture:** R3d + `blla -d horizontal-rl` (0.419) is best overall, and best on `printed_letter` (0.172 against Tesseract's 0.177), `archive_card` and `ledger`. R3d + Tesseract lines wins `handwritten_note` (0.163).
- **eval-mixed-heldout:** R3d + Tesseract lines (0.196) is best overall and on both handwritten templates. Tesseract alone still wins both printed templates (0.171 and 0.152); R3d + `blla` is next on them (0.258 and 0.232).

### Reading

- **R3d reads Latin.**
  - On (e), Latin-letter CER falls from 0.787 to 0.045 on the hocrgen fixture and from 0.774 to 0.039 on eval-mixed-heldout. Lines that contain Latin go from 0.190 to 0.065 and from 0.270 to 0.033.
  - The fixture's Latin words are almost all absent from R3d's training text, so this is reading Latin script, not recalling training words.
  - Digits improve too (0.079 → 0.014 and 0.311 → 0.033).
- **No cost on Hebrew-only pages.** On seed-101 and held-out, R3d matches R3c within 0.001 CER on `blla` and (e), with page counts balanced either way.
- **The mixed-script gain carries end to end.** With `blla`, R3d improves every fixture page over R3c (0.465 → 0.419) and 62 of 80 eval-mixed-heldout pages (0.298 → 0.229). R3d is now better than Tesseract alone on both mixed batches overall, but not on printed templates of eval-mixed-heldout.
- **What is left is segmentation, and the fixture's conventions.**
  - (e) is 0.014 on eval-mixed-heldout against 0.229 with `blla`.
  - On the fixture, most of the (e) residual (0.140) is the ` | ` cell-separator convention. The `blla` residual is mostly reading order, as for R3c (the R3c section's gold-order row).
- **Some of the fixture gain is the new templates.** R3d trained on `archive_card` and `ledger`, which R3c never saw, and its `archive_card` (e) CER falls from 0.077 to 0.028. eval-mixed-heldout has only the four shared templates, so its gain is the training text alone.
- **Crop style is still split, but R3d narrows it.**
  - On hocrsyngen's polygons (d), R3d halves R3c's Hebrew-only gap (0.041 → 0.028 and 0.045 → 0.024). It still loses to R3b there, but beats R3b on both mixed batches (0.042 against 0.097 on eval-mixed-heldout), where R3b's Latin errors dominate.
  - On Tesseract's rectangles, R3d and R3c write Latin letters that are not on the page. Mixing crop styles in training (R3e) remains the open experiment.
- **The next lever is the trained segmenter (R4d) with R3d.** R3d + R4c-e01 was not run.

### Run identities

| Part | Identity |
|---|---|
| heocr-engine | training `cade9c8`; diagnostics and conversion `aa67fa7` |
| Training batch | hocrsyngen `db3f73c` (`s11b-ledger-fit-v1`), Pillow 13.0.0 with raqm. 2,400 pages, seed 7101, seven templates round robin. Corpus `e4384322e167f81252f28703206f180d1757e789c3ef7bd97484eef6978b1cf4` (S10b `hebrew_lines_train_v1.txt` `a3f2f0db…` then S13a `hebrew_mixed_lines_train_v1.txt` `203df9e8…`). Manifest `e8098844b7dfb7027913d7a04e4a5d35100ab551d41bb759ec92f0f685c2ec73`, line annotations `51cab2f331607035f8a697ca3ffdcbff40241a65821fb4634dd80412b4e59c43` |
| Training | R3c's ketos settings and data path (`--line-polygons kraken --polygonizer-height 1800`), Kraken 7.0.2; split seed 0, validation fraction 0.05. Train 2,280 pages / 38,327 lines, validation 120 / 1,927; alphabet 107; the polygonizer drops 1 training line. mps, seed 42, not deterministic. Record `run_r3d_s7101.record.json` (validates) |
| Training outcome | Early stopping after 9 epochs; best epoch 5 (0-based), val_accuracy 0.9962 on R3d's own mixed validation split, not comparable with R3c's 0.9976 |
| Model | `best_0.9962.safetensors`, sha256 `374f9302eba092f67c06af0be2ef04c4ad528e4f60a11c2255a2bd3a75c0c889`, 16,151,296 bytes; licence `Needs verification`, unpublished |
| Inference | as R3c: Kraken 7.0.2 on cpu, `blla` `77a638a83c9e5356…`, `-f page ocr --reorder --base-dir R`; Tesseract 5.5.3 |
| hocrgen | `2d3efb0` for seed-101, held-out and eval-mixed-heldout CER; `c8fb74e` (main) for paired accounting and the hocrgen fixture |
| eval-mixed-heldout | hocrsyngen `db3f73c`, seed 8101, packaged `hebrew_mixed_lines_eval_v1.txt` (`45a81fff…`). Manifest `aff27b75c78d12e07462cbe2596e89310e96a94bf851b39863a517ee1de79047`, line annotations `2e54cbbef47959b89d05ab1a265469f3ab5ec8ea32b5db732de2643fe38c6d4e` |
| R3d prediction sets, seed-101 | `blla -d horizontal-rl` `f119f81e69c8ce5c…`, Tesseract lines `9e26b6a17bd27674…`, (e) `3a4dfba01df299f2…`, (d) `062f6283bfef4e72…` |
| R3d prediction sets, held-out | `blla -d horizontal-rl` `51545434120733e1…`, Tesseract lines `410b1f2052fd356b…`, (e) `8da14cd1fb83ee8a…`, (d) `aa7b7ea926706849…` |
| R3d prediction sets, hocrgen fixture | `blla -d horizontal-rl` `2229cd21dc07d036…`, Tesseract lines `1b92cd974a231c4d…`, (e) `885ba230e1df2eda…`, (d) `b883f46ab9165c61…` |
| eval-mixed-heldout prediction sets | Tesseract `heb+eng` `6750031f46e0507b…`. `blla -d horizontal-rl`: R3b `d50f6cc4a4e76c8b…`, R3c `74f8a7f00887476a…`, R3d `678f920229a1e611…`. Tesseract lines: R3b `ae607e61c8e96a30…`, R3c `898eac7a70e9e371…`, R3d `a0b503dfc887dddc…`. (e): R3b `9563097d160759ca…`, R3c `e41c98d60114a885…`, R3d `344ae1a6e4eeb7f3…`. (d): R3b `4f1acd60f1fa9222…`, R3c `48b4573141a9a5d5…`, R3d `01626ebf141d78ad…` |

Limits: the R3c limits apply. One training run, one seed per batch, and no confidence intervals. R3d changes both the training text and the template mix, so the hocrgen fixture's gain cannot be split between them. eval-mixed-heldout separates the text change, but it shares the training generator, fonts and 153 Latin words. Predictions, line files and reports stay local.

## R4d: trained segmenter with a learned line order (2026-11-04)

R4d is R4c's segmenter recipe, run to completion, with two data changes:
- Training regions are the S11a sidecar region polygons (`region_geometry: "sidecar"`, eight region types including `table_cells`).
- Lines inside `stamp_area` regions get their own line type `stamp` (`--line-type stamp_area=stamp`, #16).

A line-level reading-order model (`ketos rotrain`) was then trained on R4d's own training pages. The opt-in `--api python` stage (#19) applies it. Recognition is R3d throughout. Decision 0008 applies: licence `Needs verification`, not published.

### Training

- **Segmenter:** early stopping after 29 epochs. Best epoch 20, `val_mean_iu` 0.8618 (R4c epoch 1: 0.761); it stays between 0.854 and 0.862 from epoch 9 on. Baseline P / R / F1 at the best epoch: 0.9994 / 0.9800 / 0.9890.
- **Reading order:** `ketos rotrain --level baselines` on the same 1,710 / 90 pages, with lines in gold order and the segmenter's line classes (`default` 2, `stamp` 3). Early stopping after 72 epochs, about 15 s each on mps. Best `val_spearman` 0.0320, against 0.105 after the first epoch. `val_spearman` is Kraken's normalised Spearman footrule distance on the validation pages, so lower is better.

### Line geometry (`diagnose-segmentation`, polygon IoU ≥ 0.5)

The `-d horizontal-rl` rows use `kraken segment -bl`, and only the model differs. The `blla` and R4c rows are the R4c section's. The learned-order row scores the `--api python` stage's geometry files directly (`<page_sha256>.json`, see `docs/segmentation_diagnostic.md`). It has the same lines as the R4d CLI row, but in the learned order.

| Segmenter | Batch | P / R / F1 | Split gold lines | Merging predicted lines (gold lines merged) | Missed | Spurious | Kendall τ | Adjacent pairs kept | Pages fully in order | F1, `--match baseline` |
|---|---|---|---|---|---|---|---|---|---|---|
| `blla -d horizontal-rl` | seed-101 | 0.733 / 0.800 / 0.765 | 78 | 16 (32) | 27 | 1 | 0.838 | 0.866 | 26 / 80 | 0.842 |
| R4c epoch 1 `-d horizontal-rl` | seed-101 | 0.926 / 0.897 / 0.911 | 14 | 27 (54) | 5 | 0 | 0.860 | 0.862 | 13 / 80 | 0.949 |
| R4d `-d horizontal-rl` | seed-101 | 0.913 / 0.914 / 0.913 | 19 | 14 (28) | 1 | 0 | 0.819 | 0.824 | 9 / 80 | 0.995 |
| R4d, learned order (`--api python`) | seed-101 | 0.913 / 0.914 / 0.913 | 19 | 14 (28) | 1 | 0 | 1.000 | 1.000 | 80 / 80 | 0.995 |
| `blla -d horizontal-rl` | held-out | 0.624 / 0.726 / 0.671 | 96 | 4 (8) | 28 | 0 | 0.811 | 0.858 | 31 / 80 | 0.773 |
| R4c epoch 1 `-d horizontal-rl` | held-out | 0.912 / 0.886 / 0.899 | 5 | 5 (10) | 20 | 2 | 0.872 | 0.863 | 14 / 80 | 0.951 |
| R4d `-d horizontal-rl` | held-out | 0.915 / 0.916 / 0.915 | 4 | 4 (8) | 0 | 1 | 0.865 | 0.849 | 12 / 80 | 0.998 |
| R4d, learned order (`--api python`) | held-out | 0.915 / 0.916 / 0.915 | 4 | 4 (8) | 0 | 1 | 1.000 | 1.000 | 80 / 80 | 0.998 |

- **Line finding:** R4d matches R4c-e01's polygon F1 (0.913 and 0.915, against 0.911 and 0.899) but finds lines more completely.
  - Baseline-match F1 rises to 0.995 and 0.998, against 0.949 and 0.951.
  - Missed gold lines fall from 5 to 1 and from 20 to 0.
  - On seed-101, merging predicted lines are halved (27 → 14).
- **Stamps are fixed:** R4d matches 25 of the 40 stamp lines on seed-101 and 35 of 40 on held-out; R4c-e01 matches 1 on each. On seed-101 it merges 8, against 27 for R4c-e01. The `stamp` line type and the region polygons together separate them from the body lines they overlap.
- **Kraken's heuristic order is worse with R4d,** clearly on seed-101 (Kendall τ 0.819, 9 / 80 pages fully in order) and slightly on held-out (0.865, 12 / 80).
  - The footer pairs from R4c remain.
  - Separated stamp lines are a new source of error. The heuristic now orders them, and it reads them before the body lines around them: 70 discordant pairs on seed-101, against 3 for R4c-e01, which merged most stamps into body lines.
- **The learned order is perfect on both batches:** Kendall τ 1.000, and every page is fully in order over the matched lines. Both batches use the training templates (see Limits); the fixture's `archive_card` rows below are where it fails.

**Discordant pairs over matched lines** (`--lines`, against gold line order; the three most frequent kinds):

| Segmenter | Seed-101 | Held-out |
|---|---|---|
| `blla -d horizontal-rl` | 121: `signature_area` after `footer` 87, margin after `footer` 21, body after `stamp_area` 13 | 119: `signature_area` after `footer` 84, margin after `footer` 17, `stamp_area` after `signature_area` 12 |
| R4c epoch 1 | 131: `signature_area` after `footer` 95, margin after `footer` 31, body after `stamp_area` 3 | 117: `signature_area` after `footer` 81, margin after `footer` 32 |
| R4d | 177: `signature_area` after `footer` 71, body after `stamp_area` 70, margin after `footer` 36 | 134: `signature_area` after `footer` 67, margin after `footer` 33, body after `stamp_area` 29 |
| R4d, learned order | 0 | 0 |

### Seed-101 and held-out, end to end (R4d + R3d, `primary.v1` CER / WER)

R4d segments and R3d recognizes through `--api python` on cpu. Heuristic order is Kraken's line order, which gives the CLI's text (see "Python-API checks" below). Learned order is the same lines in the order the reading-order model gives. Comparison rows are from the R3c and R3d sections.

| Lines | Kind | Seed-101 | Held-out |
|---|---|---|---|
| R3d + `blla -d horizontal-rl` (R3d section) | pipeline | 0.167 / 0.292 | 0.240 / 0.405 |
| R3c + R4c-e01, preview (R3c section) | pipeline | 0.096 / 0.172 | 0.143 / 0.295 |
| R4d + R3d, heuristic order | pipeline | 0.098 / 0.151 | 0.111 / 0.162 |
| R4d + R3d, learned order | pipeline | **0.019 / 0.055** | **0.009 / 0.032** |
| R3d (e) gold baselines, Kraken polygons at height 1800, gold order (R3d section) | diagnostic | 0.018 / 0.040 | 0.006 / 0.020 |

**By template (`primary.v1` CER / WER), R4d + R3d:**

| Template | Seed-101 heuristic | Seed-101 learned | Held-out heuristic | Held-out learned |
|---|---|---|---|---|
| `printed_letter` | 0.112 / 0.182 | 0.021 / 0.065 | 0.110 / 0.184 | 0.011 / 0.037 |
| `printed_letter_heavy_scan` | 0.106 / 0.179 | 0.025 / 0.070 | 0.108 / 0.171 | 0.004 / 0.013 |
| `handwritten_note` | 0.081 / 0.107 | 0.011 / 0.032 | 0.115 / 0.131 | 0.010 / 0.031 |
| `handwritten_note_heavy_wear` | 0.084 / 0.113 | 0.015 / 0.041 | 0.113 / 0.150 | 0.013 / 0.050 |
| overall | 0.098 / 0.151 | 0.019 / 0.055 | 0.111 / 0.162 | 0.009 / 0.032 |

**Paired accounting (E2c6, learned against heuristic order; pages improved / unchanged / worsened, character edits):** seed-101 80 / 0 / 0, 1,413 → 271; held-out 80 / 0 / 0, 1,119 → 92.

- **The learned order removes almost all of the remaining error.** Seed-101 goes from 0.098 to 0.019 and held-out from 0.111 to 0.009. Every page improves on both batches.
- That is within 0.003 CER of R3d's own (e) gold-line, gold-order diagnostic (0.018 and 0.006), now from a pipeline. The previous best pipeline was R3c + R4c-e01 (preview) at 0.096 and 0.143.
- Without the learned order, R4d + R3d (0.098 and 0.111) is already about level with R3c + R4c-e01 on seed-101 and better on held-out.

### Python-API checks

- **Parity:** with R4d + R3d, the `--api python` stage without a reading-order model gives text identical to the default CLI stage on 4 of 4 seed-101 pages (one per template). R4a's mixed-batch runs repeat the check at scale (below).
- **One file for segmentation and reading order:** in Kraken 7.0.2 the way to ship them together is `ketos convert -o seg_ro.safetensors seg.safetensors ro.safetensors`, a safetensors file that holds both models.
  - Passed as both `--segmentation-model` and `--reading-order-model`, it gives text identical to the separate files on 4 of 4 seed-101 pages, with the same lines moved.
  - `ketos roadd` cannot be used with this run's models (below).

### Kraken 7.0.2 issues found in R4d (not reported upstream yet)

Reporting them, like the `line_orders` issue in the Kraken section, needs the maintainer's go-ahead. The R4d runs work around each one.

1. **`ketos rotrain --class-mapping-from-ckpt` always fails** with "--class-mapping and --class-mapping-from-ckpt are mutually exclusive". ketos's built-in defaults (`default_map`) always set rotrain's `class_mapping`.
   - Workaround: pass the segmenter's line classes in a config file, `ketos --config rotrain.yaml rotrain …` with `{"rotrain": {"class_mapping": [["default", 2], ["stamp", 3]]}}`.
   - The mapping must equal the segmenter's: at inference, `neural_reading_order` one-hot encodes line types with the segmentation model's mapping.
2. **`--class-mapping-from-ckpt` also reads `hparams["data_config"]`,** which `ketos segtrain` checkpoints do not have. Their hparams hold only `config`, and the mapping is in `net.user_metadata["class_mapping"]`. So it would fail on these checkpoints even without issue 1.
3. **`ketos roadd` cannot read a safetensors segmenter.** It loads it with the CoreML-only `TorchVGSLModel.load_model` ("Failure parsing model protobuf"), and it writes CoreML.
4. **`roadd`'s CoreML output cannot be loaded by Kraken 7.0.2 itself.** R4d was converted to CoreML first (`ketos convert --weights-format coreml`) and then given to `roadd`. `kraken.models.load_models`, and so `SegmentationTaskModel.load_model` and the CLI, reject the result ("Unexpected key(s) … `nn.ro_model_mlp_lin_*`"). The `--api python` stage fails closed on it. Use `ketos convert` instead (above).

### Mixed-script batches (R4d with R3d)

These are the two mixed-script batches from the R3d section: hocrgen's 100-page fixture and the 80-page eval-mixed-heldout. Neither is trained on. Both are scored on synthetic gold only (decision 0004).

R4d segments and R3d recognizes in three line orders:
- **Kraken order:** `segment -bl -d horizontal-rl` with R4d, then `ocr --reorder --base-dir R` with R3d, in the order Kraken emits the lines. Run through the CLI and again through `--api python`; the two give the same text (below).
- **Learned order:** the same lines in the order R4d's reading-order model gives (`--api python --reading-order-model`).
- **Gold order (diagnostic):** R4d's own lines and text, re-sorted into gold reading order by polygon anchors. It uses gold, so it is not a pipeline. It shows what a perfect order would give with R4d's lines.

Kinds and scoring are as in the R3c section. R3d + `blla -d horizontal-rl`, Tesseract lines, (e) and (d) are the R3d section's rows.

**hocrgen fixture, `primary.v1` CER per family** (hocrgen `c8fb74e`):

| Lines | Kind | Recognizer | `printed_letter` | `handwritten_note` | `archive_card` | `ledger` | overall CER / WER |
|---|---|---|---|---|---|---|---|
| Tesseract `heb+eng` alone (recipe baseline) | pipeline | Tesseract | 0.177 | 0.737 | 0.444 | 0.770 | 0.575 / 0.723 |
| `blla -d horizontal-rl` | pipeline | R3d | 0.172 | 0.181 | 0.332 | 0.657 | 0.419 / 0.598 |
| Tesseract `heb` lines | pipeline | R3d | 0.266 | 0.163 | 0.534 | 0.829 | 0.552 / 0.744 |
| R4d, Kraken order | pipeline | R3d | 0.142 | 0.125 | **0.211** | 0.580 | 0.346 / 0.522 |
| R4d, learned order | pipeline | R3d | **0.067** | **0.061** | 0.274 | **0.534** | **0.313 / 0.492** |
| R4d, gold order | diagnostic | R3d | 0.076 | 0.061 | 0.034 | 0.259 | 0.146 / 0.266 |
| (e) at height 1800 | diagnostic | R3d | 0.059 | 0.057 | 0.028 | 0.259 | 0.140 / 0.260 |
| (d) | diagnostic | R3d | 0.068 | 0.074 | 0.048 | 0.276 | 0.156 / 0.316 |

Bold marks the best pipeline per column.

**eval-mixed-heldout, `primary.v1` CER / WER per template** (hocrgen `c8fb74e`; the Kraken-order CLI row and the R3d rows were scored with `2d3efb0`, whose `scored` block is identical):

| Lines | Kind | Recognizer | `printed_letter` | `printed_letter_heavy_scan` | `handwritten_note` | `handwritten_note_heavy_wear` | overall |
|---|---|---|---|---|---|---|---|
| Tesseract `heb+eng` alone | pipeline | Tesseract | 0.171 / 0.278 | 0.152 / 0.236 | 0.775 / 0.963 | 0.794 / 0.983 | 0.425 / 0.562 |
| `blla -d horizontal-rl` | pipeline | R3d | 0.258 / 0.457 | 0.232 / 0.410 | 0.187 / 0.311 | 0.230 / 0.380 | 0.229 / 0.396 |
| Tesseract `heb` lines | pipeline | R3d | 0.269 / 0.487 | 0.250 / 0.435 | 0.117 / 0.308 | 0.099 / 0.228 | 0.196 / 0.379 |
| R4d, Kraken order | pipeline | R3d | 0.110 / 0.191 | 0.117 / 0.188 | 0.111 / 0.142 | 0.123 / 0.175 | 0.115 / 0.176 |
| R4d, learned order | pipeline | R3d | **0.013** / 0.041 | **0.012** / 0.038 | **0.020** / 0.049 | **0.025** / 0.077 | **0.016 / 0.050** |
| R4d, gold order | diagnostic | R3d | 0.015 / 0.043 | 0.012 / 0.038 | 0.020 / 0.049 | 0.025 / 0.077 | 0.017 / 0.050 |
| (e) at height 1800 | diagnostic | R3d | 0.009 / 0.031 | 0.011 / 0.033 | 0.019 / 0.051 | 0.020 / 0.062 | 0.014 / 0.043 |
| (d) | diagnostic | R3d | 0.037 / 0.144 | 0.062 / 0.214 | 0.029 / 0.098 | 0.033 / 0.092 | 0.042 / 0.143 |

Bold marks the best pipeline per column.

**CLI and `--api python` give the same text.** For Kraken order, the `--api python` stage (heocr-engine `129c58e`) reproduces the CLI rows:
- eval-mixed-heldout: 80 of 80 pages identical.
- Fixture: 99 of 100 identical. One page differs in two lines by one or two recognized characters (9,486 against 9,485 character edits, the same CER to three places).

The learned-order rows therefore differ from the Kraken-order rows only in line order.

**R4d's lines are close to gold.** Line counts on the fixture, R4d (`blla`) against gold:

| Family | Gold | R4d | `blla` |
|---|---|---|---|
| `printed_letter` | 261 | 264 | 286 |
| `handwritten_note` | 169 | 168 | 170 |
| `archive_card` | 375 | 375 | 381 |
| `ledger` | 1,500 | 1,507 | 1,492 |

In gold order, R4d's lines score within 0.006 CER of (e) on both batches (0.146 against 0.140, and 0.017 against 0.014). Nearly all of the Kraken-order error is therefore reading order.

**By script.** These are the same page projections as in the R3d section: CER on Latin letters, ASCII digits and Hebrew letters, with reference counts in brackets.

| Batch | Lines | Latin letters | Digits | Hebrew letters |
|---|---|---|---|---|
| hocrgen fixture (1,795 / 5,119 / 11,958) | Tesseract `heb+eng` alone | 0.892 | 0.668 | 0.381 |
| | R3d + `blla -d horizontal-rl` | 0.060 | 0.541 | 0.176 |
| | R3d + R4d, Kraken order | 0.050 | 0.441 | 0.105 |
| | R3d + R4d, learned order | 0.050 | 0.414 | 0.096 |
| | R3d + R4d, gold order (diagnostic) | 0.047 | 0.024 | 0.013 |
| | R3d (e) (diagnostic) | 0.045 | 0.014 | 0.008 |
| eval-mixed-heldout (873 / 750 / 6,566) | Tesseract `heb+eng` alone | 1.378 | 0.636 | 0.448 |
| | R3d + `blla -d horizontal-rl` | 0.094 | 0.165 | 0.232 |
| | R3d + R4d, Kraken order | 0.044 | 0.043 | 0.106 |
| | R3d + R4d, learned order | 0.044 | 0.043 | 0.004 |
| | R3d + R4d, gold order (diagnostic) | 0.044 | 0.043 | 0.005 |
| | R3d (e) (diagnostic) | 0.039 | 0.033 | 0.002 |

Order moves whole lines, so it charges whichever script those lines hold.
- On eval-mixed-heldout, the misordered lines are Hebrew, and learned order removes that error (0.106 → 0.004).
- On the fixture, the remaining digit error is mostly `ledger` (0.527 digit CER with learned order, against 0.005 in gold order).

**Paired accounting (E2c6, hocrgen `c8fb74e`; pages improved / unchanged / worsened, character edits baseline → candidate):**

| Candidate against baseline | hocrgen fixture | eval-mixed-heldout |
|---|---|---|
| R4d Kraken order against R3d + `blla -d horizontal-rl` | 88 / 1 / 11, 11,495 → 9,486 | 77 / 2 / 1, 2,379 → 1,195 |
| R4d Kraken order against Tesseract alone | 90 / 2 / 8, 15,780 → 9,486 | 62 / 2 / 16, 4,414 → 1,195 |
| R4d learned order against R4d Kraken order (`--api python`) | 69 / 3 / 28, 9,485 → 8,601 | 80 / 0 / 0, 1,195 → 170 |
| R4d learned order against R3d + `blla -d horizontal-rl` | 91 / 0 / 9, 11,495 → 8,601 | 80 / 0 / 0, 2,379 → 170 |
| R4d learned order against R3d + Tesseract lines | 99 / 1 / 0, 15,161 → 8,601 | 80 / 0 / 0, 2,030 → 170 |
| R4d learned order against Tesseract alone | 100 / 0 / 0, 15,780 → 8,601 | 80 / 0 / 0, 4,414 → 170 |

R4d's learned order against Kraken order, fixture pages by family (improved / unchanged / worsened): `printed_letter` 25 / 0 / 0, `handwritten_note` 24 / 1 / 0, `ledger` 20 / 2 / 3, `archive_card` 0 / 0 / 25.

**The learned order makes every fixture `archive_card` worse (0.211 → 0.274).**
- **What it does:** the `archive_card` gold reads the body lines, then the left label column (`מקור`, `תאריך`, `מספר`, `הערה`, `ארכיון`), then the footer. Kraken order keeps the five labels together on 24 of 25 pages. The reading-order model keeps them together on none: it interleaves the labels with the body lines by height.
- **Probable cause (untested):** a layout the model was not trained on. R4e (below) tested this and found otherwise: the model could not see region identity, and a model given region classes fixes the cards.
  - The reading-order model trained on R4d's batch (`train_batch_s5101`). That batch includes `archive_card_identifier_v1`, with the same gold order.
  - Its cards (generator `s10c-gold-complete-v1`) average 3.67 body lines (3 to 6, over 514 samples of both card recipes).
  - Every fixture card (`s11b-ledger-fit-v1`) has 6 longer mixed-script body lines, which run down beside the label column.
- **What would test it:** training or scoring the reading-order model on `s11b` card layouts. Not run.

**`ledger`: order and the cell separator.** Raw NFC character edits on the fixture's 25 `ledger` pages, against the gold as is and with ` | ` replaced by a line break (one cell per line; see hocrgen#98):

| Lines | Gold as is | One cell per line |
|---|---|---|
| R3d + `blla -d horizontal-rl` | 7,875 | 6,120 |
| R3d + R4d, Kraken order | 6,983 | 4,895 |
| R3d + R4d, learned order | 6,429 | 4,260 |
| R3d + R4d, gold order (diagnostic) | 3,122 | 137 |
| R3d (e) (diagnostic) | 3,112 | 130 |

Even in gold order, about 3,000 `ledger` edits are the ` | ` convention. Apart from that convention, R4d's `ledger` lines are as good as (e). What remains for a pipeline is cell order, which the learned order improves only a little (4,895 → 4,260 edits, against 137 in gold order).

### Mixed-script reading

- **R4d is the best segmenter on both mixed batches.**
  - In Kraken order, R3d + R4d is the best pipeline on both batches (0.346 and 0.115). It beats R3d + `blla` on 88 and 77 pages and Tesseract alone on 90 and 62.
  - Its line counts are within 7 of gold on every family, where `blla` over-splits printed letters (286 against 261).
- **The learned order closes the order gap on eval-mixed-heldout.**
  - CER goes from 0.115 to 0.016, with every page improved, and every template is at or below 0.025.
  - That is the same as gold order (0.017) and within 0.002 of (e). R3d + R4d + learned order is, end to end, as good as R3d on gold lines for the four benchmark templates.
  - It also beats Tesseract alone on both printed templates by an order of magnitude (0.013 and 0.012 against 0.171 and 0.152).
- **On the fixture it helps letters and notes, but not cards or ledgers.**
  - `printed_letter` and `handwritten_note` reach gold-order CER.
  - `archive_card` regresses on every page (cause above, untested), and `ledger` cell order is mostly unsolved.
  - Overall 0.346 → 0.313, against 0.146 in gold order.
- **Next levers:**
  - A reading-order model trained on the mixed layouts (`archive_card`, `ledger` from `s11b`).
  - The ` | ` convention (hocrgen#98), which is about 3,000 of the fixture's remaining `ledger` edits in every row.

### Mixed-script run identities

| Part | Identity |
|---|---|
| Segmenter | R4d `best_0.8618.safetensors`, sha256 `d32cd1a8efe7354445ccfea76551cc9943ca05792c332b5865f9bec985fe7bf7`, 5,056,800 bytes (record `run_r4d_s5101.record.json`) |
| Reading order | R4d reading-order model `best_0.0320.safetensors`, sha256 `aeccae502349b6e5fdefdd6aeba58822ae5217ef73ea76cc65d956d23fcb42bf`, 4,204 bytes, passed as a separate file |
| Recognizer | R3d `best_0.9962.safetensors`, sha256 `374f9302eba092f67c06af0be2ef04c4ad528e4f60a11c2255a2bd3a75c0c889` |
| Kraken order, CLI | Kraken 7.0.2 on cpu (executable `58ff77e3…`): `segment -bl -d horizontal-rl -i R4d ocr -m R3d --reorder --base-dir R`, lines in document order, assembled as the R3d rows |
| Kraken and learned order, `--api python` | heocr-engine `129c58e` (`claude/r4d2-parity`), `kraken-python` stage on cpu; learned order with `--reading-order-model` |
| Gold order | R4d's CLI lines re-sorted into gold order by polygon anchors (R4a's `assemble.py`, `gold:`) |
| hocrgen | `c8fb74e` (main) for every R4d row and all paired accounting. eval-mixed-heldout Kraken order (CLI) was scored with `2d3efb0`; `c8fb74e` gives an identical `scored` block |
| Batches | as in the R3d section: hocrgen fixture (`s11b-ledger-fit-v1`) and eval-mixed-heldout (hocrsyngen `db3f73c`, seed 8101) |
| R4d prediction sets, hocrgen fixture | Kraken order CLI `3e78e309cde106c3…`, Kraken order `--api python` `26688aa7519dd508…`, learned order `c12cd66cf9196efb…`, gold order `a08840877b42bf04…` |
| R4d prediction sets, eval-mixed-heldout | Kraken order CLI `02e38f450ed7bc61…`, Kraken order `--api python` `e2eec4c74e8223a7…`, learned order `f6c96bf895218f4f…`, gold order `0ccf90053cf270cd…` |

### Run identities

| Part | Identity |
|---|---|
| heocr-engine | segmenter training `aa67fa7` (main, includes #16); `--api python` runs and diagnostics `129c58e` / `eed1839` (#22) |
| Training data | `train_batch_s5101_regions`, generated with hocrsyngen `8698895` (#76, S11a region polygons; `GENERATOR_VERSION` `s10c-gold-complete-v1`, as recorded in every sample's `generator_version`; 1,800 samples). Manifest `29dffcca…` (identical to `train_batch_s5101`); annotations `871355fd…` (adds the S11a region polygons). Split as R3b (by sample, split seed 0, validation fraction 0.05): 1,710 / 90 pages. Line types: training `default` 26,510 and `stamp` 977; validation 1,501 and 52 |
| Generator note | hocrsyngen #78 (S11b, `s11b-ledger-fit-v1`) changed how ledger pages render, after this batch was made. Batches generated after #78 render ledger pages differently, including R3d's training batch (`db3f73c`) and the hocrgen fixture. R4d's training pages therefore do not show those ledger layouts (see the fixture's `ledger` rows above) |
| Segmenter training | ketos 7.0.2 `segtrain` from scratch, default network, lr 0.0002, AdamW, constant schedule, no augmentation, `quit early` with lag 8 and min-epochs 10, mps, seed 42, not deterministic. Record `run_r4d_s5101.record.json` (validates) |
| Segmenter | `best_0.8618.safetensors`, sha256 `d32cd1a8efe7354445ccfea76551cc9943ca05792c332b5865f9bec985fe7bf7`, 5,056,800 bytes |
| Reading-order training | ketos 7.0.2 `rotrain -f page --level baselines`, the class mapping by `--config` (issue 1), lr 0.001 (default), `quit early` with lag 5 and min-epochs 5, mps, seed 42, on R4d's segmentation PAGE XML |
| Reading-order model | `best_0.0320.safetensors`, sha256 `aeccae502349b6e5fdefdd6aeba58822ae5217ef73ea76cc65d956d23fcb42bf`, 4,204 bytes |
| Combined file | `ketos convert` of the two: sha256 `74afdf1c61aa10a2a446ab019490a9c9fd3fe14d1022d4a7137c2ed899a5464a` |
| Recognizer | R3d `best_0.9962.safetensors` (`374f9302…`) |
| Inference | Kraken 7.0.2 on cpu: `segment -bl -d horizontal-rl` for the CLI geometry rows; `--api python` (`kraken-python`, `base_dir` R) for the text rows and the learned-order geometry |
| hocrgen | `2d3efb0` for seed-101 and held-out |
| Batches | as R4a |
| R4d prediction sets (hocrgen `set_sha256`) | seed-101 heuristic `aea91d9011f88f7e…`, learned `4a7f7a73e6fc8a34…`; held-out heuristic `115155e7103ed4fc…`, learned `a4574f731f40b6c4…` |
| R4d line-file sets (`diagnose-segmentation` `set_sha256`) | CLI PAGE XML: seed-101 `4007cbcb51555537…`, held-out `b2de6c90888fbbbd…`. Learned-order geometry: seed-101 `a53d14a8ccc55bab…`, held-out `7f62e45f722fc648…` |

Limits:
- One segmenter run and one reading-order run, one seed per batch, no confidence intervals.
- Seed-101 and held-out use the four templates R4d trained on, from the same generator and fonts, so the perfect learned order there is in-distribution. On the fixture it makes every `archive_card` page worse; the cause given above is a hypothesis.
- The gold-order rows use gold and are not pipelines.
- Predictions, line files and reports stay local.

## R4e: reading order beyond line types (2026-11-04)

R4d's learned order is perfect on seed-101, held-out and eval-mixed-heldout. On the hocrgen fixture, though, it makes every `archive_card` worse and leaves `ledger` cell order unsolved (R4d section). R4e looked for the cause and fixed it.

- **RO-v2, more layouts** (a negative result): trained on more card and ledger layouts with the same line-typed classes, it does not help.
- **The cause is the features:** Kraken's line reading-order model cannot express card or ledger order from what it sees.
- **The fix is region-typed classes:** with each line's region type as its class, ledgers and most cards are ordered (on the development set). The `kraken-python` stage now supports this as an opt-in (#23, `--reading-order-classes region`).

End to end with R4d + R3d, the fixture's `archive_card` CER falls from 0.274 (RO-v1) to 0.052 (gold order 0.034), and the fixture overall from 0.313 to 0.146, equal to gold order. eval-mixed-heldout is unchanged at 0.016, and so are seed-101 and held-out (0.019 and 0.009).

**The fixture is now a development set for reading order.** Its `archive_card` rows guided two choices here: training RO-v2, and the region classes with stamp-first tagging. Its reading-order numbers are therefore no longer an unbiased check. eval-mixed-heldout stays the clean check, and no R4e choice was tuned on it.

**The card fix is confirmed on a clean batch.** eval-layout-heldout is a fresh batch of card, ledger and benchmark pages (seed 9101), made after A1 was fixed and run once. On it, R4d + R3d + A1 equals gold order overall (0.122). `archive_card` and `archive_card_faded_scan` reach 0.005 and 0.007, against 0.207 and 0.220 with RO-v1 (section below). Its cards are the training-style layout; the fixture's longer 6-line card is still untested on clean data.

### RO-v2: more layouts, same line classes (negative result)

- **Data:** R4d's training pages (1,710 / 90, `s10c-gold-complete-v1`) plus R3d's seven-template batch (hocrsyngen `db3f73c`, `s11b-ledger-fit-v1`, seed 7101; 2,280 / 120, R3d's split).
  - The R3d pages were prepared with `prepare-kraken-data --task segmentation --line-type stamp_area=stamp`.
  - Train 3,990 pages (565–573 per template); validation 210, including 56 `archive_card` and 30 `ledger` pages.
  - No page is in the fixture, eval-mixed-heldout, seed-101 or held-out, checked by page sha256.
- **Training:** R4d's rotrain settings and line classes (`default` 2, `stamp` 3). Early stopping after 9 epochs, best epoch 3, `val_spearman` 0.0435 on the 210 validation pages. `val_loss` was still falling, so the model is undertrained next to RO-v1's 72 epochs. But RO-v1 fails in the same way (below).
- **Model:** `best_0.0435.safetensors`, sha256 `8ffb24b969196871e0c715efaf0a2fc64b1942b22c9870a361e060dc03c43c3f`.

**Order only, on gold lines** (Kraken's `neural_reading_order` on the gold lines of each page, input shuffled with a fixed seed; mean Kendall τ against gold order and pages fully in order; a diagnostic, not a pipeline):

| Batch, template | RO-v1 (R4d) | RO-v2 |
|---|---|---|
| fixture `archive_card` | 0.830, 0 / 25 | 0.828, 0 / 25 |
| fixture `ledger` | 0.866, 0 / 25 | 0.837, 0 / 25 |
| fixture `printed_letter` | 0.996, 22 / 25 | 0.997, 23 / 25 |
| fixture `handwritten_note` | 0.998, 24 / 25 | 1.000, 25 / 25 |
| eval-mixed-heldout, seed-101, held-out (each template) | 1.000, all pages | 1.000, all pages |

**Why more layouts cannot help:** neither model has ever ordered a card or a ledger, even on pages like its training data.

| Pages fully in order, gold lines | RO-v1 | RO-v2 |
|---|---|---|
| R4d validation: `archive_card` (both recipes) / `ledger` | 0 / 19, 0 / 15 | 0 / 19, 0 / 15 |
| R3d validation: `archive_card` / `ledger` | 0 / 37, 0 / 15 | 0 / 37, 0 / 15 |
| R3d's six-body-line training cards | 0 / 13 | 0 / 13 |

- **What the gold card order needs:** it reads the body lines, then the left label column (`table_cells`, at the same heights as the body lines), then the stamp and the footer.
- **What the model sees:** Kraken's line reading-order model sees only each baseline's start, end and centre and the line's class. With line types as classes (`default` / `stamp`), nothing tells a label from a body line at the same height, so the model orders them by height and interleaves them.
- **The fixture's cards are not a new template:** they are the same recipe as the training cards, with the same region mix (title, 2 identifier lines, body, 4 labels, stamp, footer). They differ only in having 6 body lines on every card.
  - R3d's 685 cards have 3–6 body lines (mean 3.9): 3: 252, 4: 293, 5: 125, 6: 15.
  - R4d's 514 cards: 3: 241, 4: 203, 5: 67, 6: 3.

### Region-typed reading-order classes (A1)

A1, a third reading-order model, was trained with each line's region type as its class. It uses the same pages and split as RO-v2, re-prepared with `prepare-kraken-data --task segmentation --line-type REGION=REGION` for all eight regions.
- **Classes:** `default` 0, `title` 1, `body` 2, `stamp_area` 3, `signature_area` 4, `footer` 5, `margin` 6, `identifier_area` 7, `table_cells` 8.
- **Settings:** as RO-v2, except `--min-epochs 30 --lag 10`, so this run is not cut short. It ran the 30-epoch minimum; `val_spearman` reached 0 from epoch 26.
- **Model:** `best_0.0000.safetensors`, sha256 `69aa1946583bb68ddf13ef20860582f4aa982a46b2f79e38bd7d9ae20535fb56`, 8,492 bytes.

**Order only.** A1 is scored two ways. On gold lines, the lines and region tags are gold, as in the tables above. On R4d's lines, the lines are R4d's own, tagged with R4d's predicted regions by the stage's rule:
1. `stamp_area` if R4d typed the line `stamp`;
2. otherwise the first region Kraken lists for the line;
3. otherwise `default`.

The R4d-lines check uses R4d's `--api python` geometry (segmenter `d32cd1a8…`), is scored with `diagnose-segmentation --lines` over matched lines, and has the R4d baselines on the same lines next to it.

| Pages fully in order (τ) | R4d lines, heuristic | R4d lines, RO-v1 | A1, gold lines and tags | A1, R4d lines and predicted tags |
|---|---|---|---|---|
| fixture `archive_card` | 3 / 25 (0.917) | 0 / 25 (0.822) | 13 / 25 (0.991) | **15 / 25 (0.992)** |
| fixture `ledger` | 0 / 25 (0.774) | 0 / 25 (0.866) | 25 / 25 | **25 / 25** |
| fixture `printed_letter` | 0 / 25 (0.758) | 23 / 25 (0.996) | 25 / 25 | **25 / 25** |
| fixture `handwritten_note` | 1 / 25 (0.902) | 25 / 25 | 25 / 25 | **25 / 25** |
| eval-mixed-heldout | 11 / 80 (0.853) | 80 / 80 | 80 / 80 | **80 / 80** |
| seed-101 | 9 / 80 (0.819) | 80 / 80 | 80 / 80 | **80 / 80** |
| held-out | 12 / 80 (0.865) | 80 / 80 | 80 / 80 | **80 / 80** |

- **In-distribution, gold lines:** A1 orders all 210 validation pages, including every card (56) and ledger (30).
- **Predicted region types are reliable:** on matched lines, R4d's predicted type equals the gold region for 100% of lines in all four batches (fixture 2,274 / 2,274; eval-mixed-heldout 599 / 599; seed-101 585 / 585; held-out 589 / 589).
- **Stamp-first matters:** if a line simply takes the first region Kraken lists, stamps that Kraken lists under the body region are tagged `body`. Fixture `printed_letter` then falls to 7 / 25, and eval-mixed-heldout's printed templates to 16 / 20 each.
- **What is left on the cards:** every one of the 10 cards still out of order has exactly one discordant pair, the sixth and lowest body line read after the first label. Six-body-line cards are rare in training (18 of 1,199). Long cards generated from fresh seeds are the planned next step, not cards chosen to fit the fixture.

### Seed-101 and held-out, end to end (R4d + R3d, `primary.v1` CER / WER)

This runs through the stage itself: `heocr-engine` `4e09858`, `kraken-python` with `--reading-order-classes region` on cpu. It is scored against R4d's learned-order rows (RO-v1).

| Batch | RO-v1 learned order (R4d section) | A1 learned order | Pages improved / unchanged / worsened, character edits |
|---|---|---|---|
| seed-101 | 0.019 / 0.055 | 0.019 / 0.055 | 0 / 78 / 2, 271 → 274 |
| held-out | 0.009 / 0.032 | 0.009 / 0.032 | 0 / 80 / 0, 92 → 92 |

- **No regression:** order over matched lines is still Kendall τ 1.000, with every page in order on both batches.
- **The two seed-101 pages that differ** (`printed_letter_heavy_scan`) swap two short stamp fragments, such as `נב` and `בק`. These are split pieces that no gold line matches, so their order is not defined. Each page holds the same set of lines.
- **By template:** every template is within 0.001 CER of the R4d section's learned-order rows.

### Mixed-script batches, end to end (R4d + R3d with A1)

A1 is the region-typed line reading-order model. At inference each line takes the class of the R4d region it falls in (`--reading-order-classes region`). Pipeline:
- heocr-engine `4e09858`, `--api python` on cpu;
- R4d segments (`best_0.8618`), R3d recognizes;
- `--reading-order-model` A1 `--reading-order-classes region`.

Rows are compared with three orders from the R4d section:
- **Kraken order:** the heuristic order, `--api python`.
- **RO-v1:** the line reading-order model, classes from the segmenter.
- **Gold order:** a diagnostic. R4d's own lines are re-sorted into gold order by polygon anchors.

The two batches play different roles for reading order:
- **hocrgen fixture: a development set for reading order.** R4e's order-only checks were run on its gold lines while A1 was chosen, so its rows are not a clean test. It is not trained on.
- **eval-mixed-heldout: the clean check.** It was not trained on and not used to choose the model.

Both are scored on synthetic gold only (decision 0004), with hocrgen `c8fb74e`.

**hocrgen fixture (reading-order development set), `primary.v1` CER / WER per family:**

| Lines | Kind | Recognizer | `archive_card` | `ledger` | `printed_letter` | `handwritten_note` | overall |
|---|---|---|---|---|---|---|---|
| Tesseract `heb+eng` alone (recipe baseline) | pipeline | Tesseract | 0.444 / 0.617 | 0.770 / 0.867 | 0.177 / 0.257 | 0.737 / 0.932 | 0.575 / 0.723 |
| `blla -d horizontal-rl` | pipeline | R3d | 0.332 / 0.403 | 0.657 / 0.794 | 0.172 / 0.380 | 0.181 / 0.377 | 0.419 / 0.598 |
| R4d, Kraken order | pipeline | R3d | 0.211 / 0.294 | 0.580 / 0.749 | 0.142 / 0.292 | 0.125 / 0.238 | 0.346 / 0.522 |
| R4d, RO-v1 | pipeline | R3d | 0.274 / 0.304 | 0.534 / 0.735 | 0.067 / 0.200 | **0.061** / 0.175 | 0.313 / 0.492 |
| **R4d, A1 (region classes)** | pipeline | R3d | **0.052 / 0.123** | **0.260 / 0.366** | **0.062 / 0.195** | **0.061 / 0.175** | **0.146 / 0.269** |
| R4d, gold order | diagnostic | R3d | 0.034 / 0.102 | 0.259 / 0.366 | 0.076 / 0.199 | 0.061 / 0.175 | 0.146 / 0.266 |
| (e) at height 1800 | diagnostic | R3d | 0.028 / 0.089 | 0.259 / 0.366 | 0.059 / 0.173 | 0.057 / 0.185 | 0.140 / 0.260 |

Bold marks the best pipeline per column.

**eval-mixed-heldout (clean check), `primary.v1` CER / WER per template:**

| Lines | Kind | Recognizer | `printed_letter` | `printed_letter_heavy_scan` | `handwritten_note` | `handwritten_note_heavy_wear` | overall |
|---|---|---|---|---|---|---|---|
| Tesseract `heb+eng` alone | pipeline | Tesseract | 0.171 / 0.278 | 0.152 / 0.236 | 0.775 / 0.963 | 0.794 / 0.983 | 0.425 / 0.562 |
| `blla -d horizontal-rl` | pipeline | R3d | 0.258 / 0.457 | 0.232 / 0.410 | 0.187 / 0.311 | 0.230 / 0.380 | 0.229 / 0.396 |
| R4d, Kraken order | pipeline | R3d | 0.110 / 0.191 | 0.117 / 0.188 | 0.111 / 0.142 | 0.123 / 0.175 | 0.115 / 0.176 |
| R4d, RO-v1 | pipeline | R3d | **0.013** / 0.041 | **0.012** / 0.038 | **0.020** / 0.049 | **0.025** / 0.077 | **0.016 / 0.050** |
| **R4d, A1 (region classes)** | pipeline | R3d | **0.013** / 0.041 | **0.012** / 0.038 | **0.020** / 0.049 | **0.025** / 0.077 | **0.016 / 0.050** |
| R4d, gold order | diagnostic | R3d | 0.015 / 0.043 | 0.012 / 0.038 | 0.020 / 0.049 | 0.025 / 0.077 | 0.017 / 0.050 |
| (e) at height 1800 | diagnostic | R3d | 0.009 / 0.031 | 0.011 / 0.033 | 0.019 / 0.051 | 0.020 / 0.062 | 0.014 / 0.043 |

On eval-mixed-heldout, A1's text is identical to RO-v1's on all 80 pages. The region classes neither help nor hurt on the four benchmark templates, which RO-v1 already ordered at the gold-order level.

**Paired accounting (E2c6, hocrgen `c8fb74e`; pages improved / unchanged / worsened, character edits baseline → candidate):**

| A1 against | hocrgen fixture | eval-mixed-heldout |
|---|---|---|
| R4d Kraken order (`--api python`) | 99 / 1 / 0, 9,485 → 4,020 | 80 / 0 / 0, 1,195 → 170 |
| R4d RO-v1 | 53 / 46 / 1, 8,601 → 4,020 | 0 / 80 / 0, 170 → 170 |
| R3d + `blla -d horizontal-rl` | 99 / 0 / 1, 11,495 → 4,020 | 80 / 0 / 0, 2,379 → 170 |
| Tesseract alone | 100 / 0 / 0, 15,780 → 4,020 | 80 / 0 / 0, 4,414 → 170 |

Fixture pages by family, A1 against each order (improved / unchanged / worsened, character edits):

| Family | against Kraken order | against RO-v1 | against gold order |
|---|---|---|---|
| `archive_card` | 25 / 0 / 0, 1,181 → 290 | 25 / 0 / 0, 1,538 → 290 | 0 / 15 / 10, 191 → 290 |
| `ledger` | 25 / 0 / 0, 6,983 → 3,125 | 25 / 0 / 0, 6,429 → 3,125 | 0 / 24 / 1, 3,122 → 3,125 |
| `printed_letter` | 25 / 0 / 0, 810 → 356 | 3 / 21 / 1, 385 → 356 | 10 / 14 / 1, 432 → 356 |
| `handwritten_note` | 24 / 1 / 0, 511 → 249 | 0 / 25 / 0, 249 → 249 | 0 / 25 / 0, 249 → 249 |

On `printed_letter`, A1 beats gold order on 10 pages. A polygon-anchor re-sort is not a perfect order where R4d splits or merges lines, so gold order is not a strict ceiling.

**`archive_card`: the RO-v1 regression is fixed.**
- **CER:** 0.274 with RO-v1 and 0.211 in Kraken order, down to 0.052 with A1 (gold order 0.034). All 25 cards improve on both.
- **Label column:**
  - RO-v1 kept the five labels (`מקור` … `ארכיון`) together on 0 of 25 cards and Kraken order on 24. A1 keeps them together on 15.
  - Those 15 cards have the same character edits as gold order.
- **The 10 cards still off:** one mistake each. The first label, `מקור`, is placed before the last body line, which runs down beside the label column. Hebrew-letter CER on `archive_card` is 0.028, against 0.211 for RO-v1 and 0.001 in gold order.

**`ledger`: cell order is solved.** Raw NFC character edits on the fixture's 25 `ledger` pages, against the gold as is and with ` | ` replaced by a line break (one cell per line; hocrgen#98):

| Lines | Gold as is | One cell per line |
|---|---|---|
| R4d, Kraken order | 6,983 | 4,895 |
| R4d, RO-v1 | 6,429 | 4,260 |
| **R4d, A1** | **3,125** | **149** |
| R4d, gold order (diagnostic) | 3,122 | 137 |

What is left on `ledger` (about 3,000 edits) is the ` | ` convention, not order. 24 of the 25 `ledger` pages have the same character edits as gold order.

**By script (page CER; reference counts as in the R4d section):**

| Batch | Lines | Latin letters | Digits | Hebrew letters |
|---|---|---|---|---|
| hocrgen fixture | R4d, Kraken order | 0.050 | 0.441 | 0.105 |
| | R4d, RO-v1 | 0.050 | 0.414 | 0.096 |
| | R4d, A1 | 0.050 | **0.024** | **0.014** |
| | R4d, gold order (diagnostic) | 0.047 | 0.024 | 0.013 |
| eval-mixed-heldout | R4d, Kraken order | 0.044 | 0.043 | 0.106 |
| | R4d, RO-v1 | 0.044 | 0.043 | 0.004 |
| | R4d, A1 | 0.044 | 0.043 | 0.004 |
| | R4d, gold order (diagnostic) | 0.044 | 0.043 | 0.005 |

The fixture's digit error was `ledger` cell order: `ledger` digit CER falls from 0.527 with RO-v1 to 0.005 with A1, the same as gold order.

### Mixed-script reading (A1)

- **A1 reaches gold order end to end on the development set.**
  - With region classes, R3d + R4d + A1 scores 0.146 overall on the fixture: the same as gold order (0.146), within 0.006 of (e) (0.140), and down from 0.313 with RO-v1.
  - It is the best pipeline on every family and beats Tesseract alone on all 100 pages.
  - These are development-set numbers (A1 was chosen on this fixture's gold-line order checks), so they are likely optimistic for new layouts.
- **No change on the clean check.** On eval-mixed-heldout A1 gives the same text as RO-v1 on every page (0.016, gold order 0.017). Region classes cost nothing where RO-v1 was already right. eval-mixed-heldout has no `archive_card` or `ledger`, so it does not test the fix itself.
- **The RO-v1 failure was missing region identity.** The same lines, with only the line classes changed from segmenter types to R4d region types, take `archive_card` from 0.274 to 0.052 and `ledger` from 0.534 to 0.260 (the ` | ` floor).
- **What remains on the fixture:**
  - the ` | ` convention, about 3,000 `ledger` edits (hocrgen#98);
  - one misplaced label on 10 `archive_card` pages;
  - the em-dash gap (hocrsyngen#87);
  - in-line recognition errors, Latin letters 0.050.
- **The clean test of the `archive_card` and `ledger` fix** is eval-layout-heldout (section below). It confirms the fix on training-style cards and on ledgers.

### Mixed-script run identities (A1)

| Part | Identity |
|---|---|
| heocr-engine | `4e09858` (#23, region-typed RO classes), own detached worktree; `kraken-python` stage, `--api python`, cpu |
| Segmenter | R4d `best_0.8618.safetensors`, sha256 `d32cd1a8efe7354445ccfea76551cc9943ca05792c332b5865f9bec985fe7bf7` |
| Recognizer | R3d `best_0.9962.safetensors`, sha256 `374f9302eba092f67c06af0be2ef04c4ad528e4f60a11c2255a2bd3a75c0c889` |
| Reading order | A1 `tasks/r4e-reading-order/a1/run_a1_ro/checkpoints/best_0.0000.safetensors`, sha256 `69aa1946583bb68ddf13ef20860582f4aa982a46b2f79e38bd7d9ae20535fb56`, 8,492 bytes, `--reading-order-classes region` |
| Comparison rows | Kraken order and RO-v1 from the R4d section (heocr-engine `129c58e`; the `kraken-python` stage is unchanged up to `5294ca5`); gold order as in the R4d section |
| hocrgen | `c8fb74e` (main), `primary.v1`, `raw.v1` and `consonantal.v1` |
| Prediction sets | hocrgen fixture A1 `88d7e1bf1d25a482…`; eval-mixed-heldout A1 `6418149af3ff1ec2…` (text identical to RO-v1 `f6c96bf895218f4f…`; the sets differ in pipeline metadata) |
| Run | every page of both batches (100 and 80), no failures; one kraken job |

### eval-layout-heldout: the clean check of region-typed reading order (2026-11-04)

The hocrgen fixture was the development set for A1, so it cannot test the fix. eval-layout-heldout is a fresh batch made for that test.

**The batch:**
- hocrsyngen main `d63b627` (`s11b-ledger-fit-v1`, the generator version of R3d's training batch and the fixture), seed 9101. The seed is not used anywhere else in HeOCR.
- 100 pages: 20 each of `archive_card`, `archive_card_faded_scan` and `ledger`, and 10 each of the four benchmark templates.
- Text from the packaged mixed-script eval corpus (`hebrew_mixed_lines_eval_v1.txt`). None of its 175 drawn corpus lines is in R3d's training text.
- It was never trained on and nothing was tuned on it. Each pipeline was run once, and A1, RO-v1 and all settings were fixed before it was generated.
- Scored on synthetic gold only (decision 0004), hocrgen `c8fb74e`.

**Pipeline:**
- R4d segments and R3d recognizes, on heocr-engine `660e5a4`, `--api python`, cpu.
- Line orders: Kraken order (heuristic), RO-v1, and A1 with `--reading-order-classes region`.
- Gold order is a diagnostic: R4d's own lines re-sorted into gold order by polygon anchors.

**`primary.v1` CER / WER per template:**

| Lines | Kind | `archive_card` | `archive_card_faded_scan` | `ledger` | `printed_letter` | `printed_letter_heavy_scan` | `handwritten_note` | `handwritten_note_heavy_wear` | overall |
|---|---|---|---|---|---|---|---|---|---|
| Tesseract `heb+eng` alone | pipeline | 0.409 / 0.598 | 0.410 / 0.613 | 0.762 / 0.853 | 0.103 / 0.170 | 0.161 / 0.261 | 0.791 / 1.000 | 0.749 / 0.976 | 0.564 / 0.725 |
| R4d + R3d, Kraken order | pipeline | 0.256 / 0.307 | 0.251 / 0.279 | 0.587 / 0.741 | 0.110 / 0.181 | 0.115 / 0.198 | 0.133 / 0.180 | 0.133 / 0.210 | 0.369 / 0.508 |
| R4d + R3d, RO-v1 | pipeline | 0.207 / 0.183 | 0.220 / 0.197 | 0.541 / 0.728 | **0.007** / 0.025 | **0.013** / 0.035 | **0.037** / 0.090 | **0.035** / 0.117 | 0.312 / 0.446 |
| **R4d + R3d, A1 (region classes)** | pipeline | **0.005 / 0.023** | **0.007 / 0.019** | **0.258 / 0.348** | **0.007 / 0.025** | **0.013 / 0.035** | **0.037 / 0.090** | **0.035 / 0.117** | **0.122 / 0.202** |
| R4d + R3d, gold order | diagnostic | 0.005 / 0.023 | 0.007 / 0.019 | 0.258 / 0.348 | 0.009 / 0.032 | 0.013 / 0.035 | 0.038 / 0.090 | 0.035 / 0.117 | 0.122 / 0.203 |

Bold marks the best pipeline per column. `raw.v1` and `consonantal.v1` give the same A1 overall (0.122 / 0.202).

**Paired accounting (E2c6, pages improved / unchanged / worsened, character edits baseline → candidate):**

| Candidate against baseline | All 100 pages |
|---|---|
| A1 against Kraken order | 100 / 0 / 0, 7,787 → 2,562 |
| A1 against RO-v1 | 60 / 40 / 0, 6,576 → 2,562 |
| A1 against Tesseract alone | 100 / 0 / 0, 11,885 → 2,562 |
| RO-v1 against Kraken order | 77 / 3 / 20, 7,787 → 6,576 |
| RO-v1 against Tesseract alone | 99 / 0 / 1, 11,885 → 6,576 |
| Kraken order against Tesseract alone | 89 / 3 / 8, 11,885 → 7,787 |

A1 by template (improved / unchanged / worsened, character edits):

| Template | against RO-v1 | against gold order |
|---|---|---|
| `archive_card` | 20 / 0 / 0, 682 → 16 | 0 / 20 / 0, 16 → 16 |
| `archive_card_faded_scan` | 20 / 0 / 0, 725 → 22 | 0 / 20 / 0, 22 → 22 |
| `ledger` | 20 / 0 / 0, 5,063 → 2,418 | 0 / 20 / 0, 2,418 → 2,418 |
| `printed_letter` | 0 / 10 / 0, 11 → 11 | 1 / 9 / 0, 14 → 11 |
| `printed_letter_heavy_scan` | 0 / 10 / 0, 18 → 18 | 0 / 10 / 0, 18 → 18 |
| `handwritten_note` | 0 / 10 / 0, 40 → 40 | 1 / 9 / 0, 41 → 40 |
| `handwritten_note_heavy_wear` | 0 / 10 / 0, 37 → 37 | 0 / 10 / 0, 37 → 37 |

**Archive cards.**
- A1 matches gold order on all 40 cards (same character edits on every page).
- The five labels (`מקור` … `ארכיון`) stay together on 39 of 40 cards with A1, Kraken order and gold order, and on 0 of 40 with RO-v1.
- RO-v1 also fails on these cards (0.207 and 0.220), although they are the training-style layout: 3.9 body lines on average, against 3.67 in RO-v1's training cards and 6 on the fixture.
- The fixture's longer card was not part of this batch. The one remaining A1 card error on the fixture (`מקור` before the last body line) is not tested here.

**`ledger`.** Raw NFC character edits on the 20 `ledger` pages, against the gold as is and with ` | ` replaced by a line break (one cell per line; hocrgen#98):

| Lines | Gold as is | One cell per line |
|---|---|---|
| R4d, Kraken order | 5,496 | 3,836 |
| R4d, RO-v1 | 5,063 | 3,315 |
| **R4d, A1** | **2,418** | **20** |
| R4d, gold order (diagnostic) | 2,418 | 20 |

With A1, every `ledger` edit but 20 is the ` | ` convention: 2,418 of A1's 2,562 edits on the whole batch.

**By script (page CER; reference letters 932 Latin, 4,704 digits, 9,036 Hebrew):**

| Lines | Latin letters | Digits | Hebrew letters |
|---|---|---|---|
| Tesseract `heb+eng` alone | 1.076 | 0.598 | 0.359 |
| R4d + R3d, Kraken order | 0.048 | 0.392 | 0.126 |
| R4d + R3d, RO-v1 | 0.048 | 0.387 | 0.101 |
| R4d + R3d, A1 | 0.048 | 0.008 | 0.002 |
| R4d + R3d, gold order (diagnostic) | 0.049 | 0.008 | 0.002 |

**Observation: CLI and `--api python` Kraken order agree** on 98 of 100 pages (7,790 against 7,787 character edits). This does not affect any A1 row; it is recorded for the stage's parity record.
- On one `handwritten_note` page, one line differs.
- On one `printed_letter` page, the CLI emits an 11th, junk line (`נבד)`, `4`) that `--api python` drops. Its polygonizer reports "failed on line 0" once per run, and the page still completes.

### Reading (eval-layout-heldout)

- **A1's fix holds on fresh pages and text.**
  - On a batch nothing was tuned on, R4d + R3d + A1 equals gold order overall (0.122 against 0.122). It matches gold order on every card and ledger page.
  - It improves every page over Kraken order, and every card and ledger page over RO-v1.
  - The fixture's development-set result (0.146 against 0.146 in gold order) is reproduced.
- **Region classes cost nothing elsewhere.** On the four benchmark templates, A1's text has the same edits as RO-v1's on all 40 pages.
- **RO-v1's card failure is not only the fixture's long card.** RO-v1 misorders training-style cards too (0 of 40 label columns together), so region identity, not card length, is what it lacked.
- **What is left is not order.**
  - Of A1's 2,562 edits, 2,418 are the ledger ` | ` convention (hocrgen#98). The rest is in-line recognition: Latin letters 0.048, archive cards 0.005 to 0.007.
  - With a one-cell-per-line gold, this batch's `ledger` would be about 20 edits.
- **Against Tesseract:** A1 is better on all 100 pages, including both printed-letter templates (0.007 and 0.013 against 0.103 and 0.161).

### Run identities (eval-layout-heldout)

| Part | Identity |
|---|---|
| Batch | `tasks/eval-layout-heldout/eval-layout-heldout`: hocrsyngen `d63b62755b391dfc6dc4b17f173f4cc62b7c50c6` (`s11b-ledger-fit-v1`), Pillow 13.0.0 with raqm, seed 9101, 100 pages. Packaged `hebrew_mixed_lines_eval_v1.txt` (`45a81fff…`). Manifest `facbe571069308c8f842d4f30d0cd946c2494061bfa1018c900a556b551e2259`, line annotations `ec93f337cf04ffe484383c046c259049e13a279231615ed58de22035086acb96`. Validates. Quality check: 22 occluded lines (20 `ledger`), 51 truncated `ledger` segments (hocrsyngen#85) |
| heocr-engine | `660e5a4` (main), `kraken-python` stage, cpu, own detached worktree. CLI rows: Kraken 7.0.2 `segment -bl -d horizontal-rl … ocr --reorder --base-dir R` |
| Models | R4d `d32cd1a8efe7354445ccfea76551cc9943ca05792c332b5865f9bec985fe7bf7`; R3d `374f9302eba092f67c06af0be2ef04c4ad528e4f60a11c2255a2bd3a75c0c889`; RO-v1 `aeccae502349b6e5fdefdd6aeba58822ae5217ef73ea76cc65d956d23fcb42bf`; A1 `69aa1946583bb68ddf13ef20860582f4aa982a46b2f79e38bd7d9ae20535fb56` (`--reading-order-classes region`) |
| Tesseract | 5.5.3, `heb+eng`, `--psm 3` |
| hocrgen | `c8fb74e` (main), `primary.v1`, `raw.v1`, `consonantal.v1` |
| Prediction sets | Tesseract `41a6a90f0d53f567…`; Kraken order CLI `a2684719ed9dc5b6…`, `--api python` `f86964c2390f4d75…`; RO-v1 `e99a10534d760da5…`; A1 `beca6e735a13326c…`; gold order `fd50511c5716f78b…` |
| Run | every set complete (100 pages each), no failures; one kraken job at a time |

Limits:
- One batch, one seed, no confidence intervals.
- Its cards are the training-style layout, not the fixture's 6-line card.
- It shares the generator, fonts and corpus family with the reading-order training data.
- Predictions and reports stay local.

### Run identities

| Part | Identity |
|---|---|
| heocr-engine | data preparation `5294ca5`; stage and end-to-end runs `4e09858` (#23) |
| RO-v2 | ketos 7.0.2 `rotrain -f page --level baselines`, mapping by `--config`, lr 0.001, `quit early` lag 5, min-epochs 5, mps, seed 42. Train / validation lists sha256 in the local run record (`run_r4e_ro.record.json`) |
| A1 | the same, with lag 10 and min-epochs 30 and the nine-class mapping above (`run_a1_ro.record.json`) |
| R3d batch | hocrsyngen `db3f73c`, manifest `e8098844…`, annotations `51cab2f3…`; split as R3d (by sample, split seed 0, validation fraction 0.05) |
| Segmenter and recognizer | R4d `best_0.8618.safetensors` (`d32cd1a8…`), R3d `best_0.9962.safetensors` (`374f9302…`) |
| Order-only check | `ro_gold_check.py` and `a2_predicted_regions.py` (local task scripts) over `prepare-kraken-data` PAGE XML of each batch. These eval-only copies are never trained on |
| A1 prediction sets, seed-101 and held-out (hocrgen `set_sha256`) | seed-101 `fbea7f8fd518042b…`, held-out `4c090e53c57c719d…` |

Limits:
- One run per reading-order model, one seed per batch, no confidence intervals.
- **The card fix is confirmed on a clean batch of training-style cards.** On eval-layout-heldout (fresh seed, nothing tuned on it), A1 matches gold order on all 40 cards and all 20 ledgers.
- **The fixture's 6-line card is still untested on clean data.** eval-layout-heldout's cards average 3.9 body lines (3 to 5), close to the training cards. The fixture's remaining A1 card error (`מקור` before the last body line) has no clean check yet.
- The gold-line rows and the gold-order rows use gold and are not pipelines.
- Predictions, line files and reports stay local.

## R3f: recognizer trained with typographic punctuation (2026-11-04)

Naming: "R3e" is already used, both on main for the crop-mix experiment and by PR #21. This run is therefore R3f. Its local task folder and run name keep the working label `r3e-typo` / `run_r3e_s7201`.

R3d's training text has no typographic punctuation (hocrsyngen#87): no `—`, `–`, `׳`, `״`, curly quotes or `…`. R3f keeps R3d's recipe exactly: from scratch, Kraken polygons at height 1800, and the same settings and early stopping. Only the training batch changes:
- **Text:** S10b Hebrew train (9,359 lines), then S13a mixed Hebrew/Latin train (5,810 lines), then S13b typographic train (4,822 lines; hocrsyngen #88). 19,991 lines in all.
- **Batch:** hocrsyngen `88ba5e6`, the same seven templates round robin, 3,000 pages, seed 7201.
- **Alphabet:** 117 characters, R3d's 107 plus `׳ ״ – — ‘ ’ “ ” „ …`. None of R3d's characters is lost.

None of the batches below is trained on: seed-101, held-out, the hocrgen fixture, eval-mixed-heldout, eval-layout-heldout and eval-typo-heldout. No page of R3f's training batch matches any of them by page sha256. The weights are not in this repository and are not published. Their licence is `Needs verification` (decision 0007).

**Decision (maintainer's lead, 2026-11-04):**
- R3d stays the default and reported recognizer. R3f is recorded as a typographic-punctuation candidate and is not promoted.
- It is not promoted because eval-mixed-heldout regresses (0.016 → 0.021, with a paired interval that excludes zero), and so do hocrsyngen's polygons (d) and Tesseract lines.
- A second R3f seed, s7202, is pending. It will tell whether those regressions come from the recipe or from run-to-run variation.

### Training

- **Stopping:** early stopping after 10 epochs. The best epoch is 6 (0-based), with val_accuracy 0.9960 on R3f's own validation split. It is not comparable with R3d's 0.9962.
- **Split:** train 2,850 pages / 47,633 lines, validation 150 pages / 2,706 lines; every template is in both.
- **Lines:** the polygonizer drops none. 1,893 of the 50,339 gold lines carry a new mark.

### Seed-101 (S10c gold) and held-out batches (`primary.v1` CER / WER, overall)

These are R3d's four line sources, unchanged; only the recognizer changes. Intervals are 95% paired page bootstrap intervals (2,000 resamples) on the change in pooled CER. Paired accounting is E2c6: pages improved / unchanged / worsened, then character edits R3d → R3f.

| Lines | Kind | R3d seed-101 | R3f seed-101 | R3d held-out | R3f held-out |
|---|---|---|---|---|---|
| `blla -d horizontal-rl` | pipeline | 0.167 / 0.292 | 0.169 / 0.294 | 0.240 / 0.405 | 0.241 / 0.408 |
| Tesseract `--psm 3` lines | pipeline | **0.194 / 0.356** | 0.216 / 0.409 | **0.196 / 0.362** | 0.248 / 0.469 |
| (e) gold baselines, Kraken polygons at height 1800, gold order | diagnostic | 0.018 / 0.040 | 0.018 / 0.047 | 0.006 / 0.020 | 0.006 / 0.025 |
| (d) gold lines with hocrsyngen's polygons, gold order | diagnostic | **0.028 / 0.096** | 0.054 / 0.151 | **0.024 / 0.106** | 0.064 / 0.167 |

| Lines | Seed-101: R3f against R3d | Held-out: R3f against R3d |
|---|---|---|
| `blla -d horizontal-rl` | 24 / 19 / 37, 2,406 → 2,434 [0.000, +0.004] | 26 / 22 / 32, 2,415 → 2,427 [−0.002, +0.004] |
| Tesseract lines | 15 / 5 / 60, 2,805 → 3,113 [+0.015, +0.028] | 9 / 5 / 66, 1,976 → 2,498 [+0.039, +0.066] |
| (e) | 20 / 31 / 29, 259 → 260 [−0.002, +0.002] | 11 / 44 / 25, 58 → 65 [−0.002, +0.003] |
| (d) | 22 / 15 / 43, 402 → 775 [+0.015, +0.039] | 17 / 19 / 44, 243 → 648 [+0.025, +0.058] |

**Where (d) loses: one template.** The other three templates stay within 0.013 of R3d. On `printed_letter_heavy_scan`:
- seed-101 goes 0.043 / 0.157 → 0.128 / 0.316;
- held-out goes 0.038 / 0.178 → 0.165 / 0.345.

On those crops R3f writes Latin letters and stray brackets that are not on the page. It also reads the stamp word `אישור` as nonsense such as `צניגצנ`. Tesseract lines lose on all four templates (held-out `printed_letter` 0.252 → 0.312).

### Best pipeline on all four batches: R4d + A1 (`primary.v1` CER / WER)

This is the R4e pipeline: the `kraken-python` stage on cpu, the R4d segmenter, and A1 with `--reading-order-classes region`. Only the recognizer changes. The R3d rows are those of the R4e section.

| Batch | R4d + R3d + A1 | R4d + R3f + A1 | R3f against R3d (pages, character edits) | 95% interval |
|---|---|---|---|---|
| seed-101 | 0.019 / 0.055 | 0.018 / 0.055 | 32 / 27 / 21, 274 → 262 | [−0.003, +0.001] |
| held-out | **0.009 / 0.032** | 0.010 / 0.034 | 17 / 41 / 22, 92 → 97 | [−0.002, +0.003] |
| hocrgen fixture (development set) | 0.146 / 0.269 | **0.130 / 0.218** | 88 / 3 / 9, 4,020 → 3,571 | [−0.020, −0.013] |
| eval-mixed-heldout | **0.016 / 0.050** | 0.021 / 0.068 | 16 / 32 / 32, 170 → 221 | [+0.001, +0.010] |

**By template:**
- **eval-mixed-heldout:**
  - `handwritten_note_heavy_wear` 0.025 → 0.041;
  - `handwritten_note` 0.020 → 0.025;
  - `printed_letter` 0.013 → 0.017;
  - `printed_letter_heavy_scan` 0.012 → 0.010.
- **hocrgen fixture:**
  - `archive_card` 0.052 → 0.034;
  - `handwritten_note` 0.061 → 0.033;
  - `printed_letter` 0.062 → 0.031;
  - `ledger` 0.260 → 0.255.

**The fixture gain is mostly the em dash.**
- The fixture's gold has 325 em dashes `—`, in 27,443 reference characters. R3d's alphabet has no `—`, so each of them costs R3d at least one edit, about 0.012 CER. R3f writes 317 em dashes.
- The other nine new marks do not occur in any of these four batches, which test them only for false insertions. eval-typo-heldout (below) is the test of the new marks.
- The fixture is also a development set: R4e tuned reading order on it. It is not a clean check.

### eval-typo-heldout: typographic punctuation, R3d baseline and R3f (2026-11-04)

R3d's training text has no typographic punctuation (hocrsyngen#87). eval-typo-heldout is a fresh batch made to measure that gap. R3f is R3d's recipe retrained on text that adds the S13b typographic corpus.

**The batch:**
- hocrsyngen main `88ba5e6` (`s11b-ledger-fit-v1`), seed 9201 (unused elsewhere).
- 80 pages, 20 each of the four benchmark templates.
- Text from the packaged S13b eval corpus, `hebrew_typographic_lines_eval_v1.txt`. None of its lines is in the S13b train corpus, R3d's training text or R3f's training text.
- The gold has 308 of the new marks (table below). Both fonts have glyphs for all of them.
- It was never trained on and nothing is tuned on it. The R3d baseline was scored once before R3f finished training. R3f was scored once, with its model fixed beforehand.
- Scored on synthetic gold only (decision 0004), hocrgen `c8fb74e`.

**Pipelines:**
- R4d + R3d + A1: the pipeline before R3f, on heocr-engine `660e5a4` with `--api python`, cpu and `--reading-order-classes region`.
- R4d + R3f + A1: the same pipeline and settings with R3f as the recognizer, on heocr-engine `c5f8034`. It has the same code as `660e5a4`; the commits between them change only docs.
- Tesseract `heb+eng` alone.

**`primary.v1` CER / WER per template:**

| Lines | `printed_letter` | `printed_letter_heavy_scan` | `handwritten_note` | `handwritten_note_heavy_wear` | overall |
|---|---|---|---|---|---|
| Tesseract `heb+eng` alone | 0.140 / 0.294 | 0.143 / 0.310 | 0.807 / 1.007 | 0.811 / 1.000 | 0.414 / 0.590 |
| R4d + R3d + A1 | 0.032 / 0.129 | 0.042 / 0.158 | 0.040 / 0.180 | 0.052 / 0.214 | 0.041 / 0.166 |
| **R4d + R3f + A1** | **0.008 / 0.037** | **0.005 / 0.027** | **0.009 / 0.046** | **0.019 / 0.077** | **0.010 / 0.044** |

**Overall CER / WER by profile:**

| Lines | `raw.v1` | `primary.v1` | `consonantal.v1` | `punct_folded.v1` (report only) |
|---|---|---|---|---|
| Tesseract `heb+eng` alone | 0.448 / 0.596 | 0.414 / 0.590 | 0.414 / 0.590 | 0.391 / 0.525 |
| R4d + R3d + A1 | 0.041 / 0.166 | 0.041 / 0.166 | 0.041 / 0.166 | 0.007 / 0.028 |
| **R4d + R3f + A1** | **0.010 / 0.044** | **0.010 / 0.044** | **0.010 / 0.044** | **0.006 / 0.024** |

`punct_folded.v1` replaces dashes with a space and deletes other punctuation.
- R3d's gap between `primary.v1` and folded was 0.034 CER: 356 of its 422 character edits were punctuation.
- R3f's gap is 0.004 (0.0095 against 0.0055). R3f's folded score is also slightly better than R3d's (0.0055 against 0.0068).

**Paired accounting (E2c6, pages improved / unchanged / worsened, character edits baseline → candidate):**

| Template | R3f against R3d (both R4d + A1) |
|---|---|
| `printed_letter` | 18 / 1 / 1, 98 → 23 |
| `printed_letter_heavy_scan` | 20 / 0 / 0, 131 → 17 |
| `handwritten_note` | 19 / 1 / 0, 88 → 20 |
| `handwritten_note_heavy_wear` | 18 / 2 / 0, 105 → 39 |
| **all 80 pages** | **75 / 4 / 1, 422 → 99** (word edits 326 → 86) |

R4d + R3f + A1 against Tesseract alone: 80 / 0 / 0, 4,305 → 99.

**Per-character rows** (gold marks after `primary.v1` normalization; page-level optimal Levenshtein alignment; "kept" means aligned to the same character; substitutes ranked by count):

| Mark | Code point | Gold | Tesseract kept | R3d kept | R3d main substitutes | **R3f kept** | R3f main substitutes |
|---|---|---|---|---|---|---|---|
| em dash `—` | U+2014 | 52 | 9 | 0 | `-` 52 | **51** | one Hebrew letter |
| en dash `–` | U+2013 | 26 | 0 | 0 | `-` 26 | **22** | `—` 4 |
| geresh `׳` | U+05F3 | 58 | 0 | 0 | `'` 55, `"` 3 | **40** | `'` 17 (1 deleted) |
| gershayim `״` | U+05F4 | 81 | 0 | 0 | `"` 78 | **79** | `"` 1, one Hebrew letter |
| left double quote `“` | U+201C | 30 | 1 | 0 | `"` 27 | **30** | — |
| right double quote `”` | U+201D | 37 | 0 | 0 | `"` 33 | **33** | `"` 2, `ף` 1, `׳` 1 |
| low double quote `„` | U+201E | 7 | 0 | 0 | `,` 3 (3 deleted) | **5** | one Hebrew letter (1 deleted) |
| left single quote `‘` | U+2018 | 5 | 0 | 0 | `"` 3 | **2** | `“` 2, one Hebrew letter |
| right single quote `’` | U+2019 | 5 | 0 | 0 | `'` 5 | **0** | `'` 5 |
| ellipsis `…` | U+2026 | 7 | 0 | 0 | `.` 6 | **6** | (1 deleted) |
| all new marks | | 308 | 10 | 0 | | **268** (87%) | |
| ASCII `"` (control) | U+0022 | 14 | 11 | 14 | | 14 | |

**Characters the pipelines add where the gold has none:**

| Character | Tesseract | R3d | R3f |
|---|---|---|---|
| hyphen-minus `-` | 81 | 106 | **0** |
| apostrophe `'` | 60 | 62 | **22** |
| quotation mark `"` | 136 | 147 | **3** |

R3d tended to write an em dash as `--`. R3f writes it as `—`.

**By script (page CER; reference characters: 335 digits, 7,559 Hebrew letters, no Latin letters):**

| Lines | Digits | Hebrew letters |
|---|---|---|
| Tesseract `heb+eng` alone | 1.343 | 0.427 |
| R4d + R3d + A1 | 0.101 (34 edits) | 0.004 (29) |
| R4d + R3f + A1 | **0.048** (16) | 0.004 (33) |

### R3f on eval-layout-heldout (2026-11-04)

This reruns the eval-layout-heldout clean check (above) with R3f instead of R3d. The pages, segmenter, A1 and settings are the same. This batch has no typographic marks: its gold uses ASCII `-`, `'` and `"`.

**`primary.v1` CER / WER per template:**

| Lines | `archive_card` | `archive_card_faded_scan` | `ledger` | `printed_letter` | `printed_letter_heavy_scan` | `handwritten_note` | `handwritten_note_heavy_wear` | overall |
|---|---|---|---|---|---|---|---|---|
| Tesseract `heb+eng` alone | 0.409 / 0.598 | 0.410 / 0.613 | 0.762 / 0.853 | 0.103 / 0.170 | 0.161 / 0.261 | 0.791 / 1.000 | 0.749 / 0.976 | 0.564 / 0.725 |
| R4d + R3d + A1 | **0.005 / 0.023** | **0.007 / 0.019** | **0.258 / 0.348** | 0.007 / 0.025 | **0.013 / 0.035** | 0.037 / 0.090 | **0.035 / 0.117** | **0.122 / 0.202** |
| R4d + R3f + A1 | 0.005 / 0.028 | 0.013 / 0.021 | 0.260 / 0.354 | **0.006 / 0.021** | 0.019 / 0.062 | **0.028 / 0.090** | 0.046 / 0.122 | 0.124 / 0.208 |

`raw.v1` and `consonantal.v1` give the same overall as `primary.v1` for both. On this batch `punct_folded.v1` is higher for both (R3d 0.127 / 0.193, R3f 0.129 / 0.198), because it also folds the ledger's ` | ` separators and the gold's ASCII hyphens.

**Paired accounting, R3f against R3d (both R4d + A1; pages improved / unchanged / worsened, character edits):**

| Template | R3f against R3d |
|---|---|
| `archive_card` | 4 / 10 / 6, 16 → 17 |
| `archive_card_faded_scan` | 2 / 15 / 3, 22 → 44 |
| `ledger` | 0 / 8 / 12, 2,418 → 2,438 |
| `printed_letter` | 2 / 5 / 3, 11 → 9 |
| `printed_letter_heavy_scan` | 1 / 5 / 4, 18 → 27 |
| `handwritten_note` | 4 / 3 / 3, 40 → 30 |
| `handwritten_note_heavy_wear` | 2 / 3 / 5, 37 → 49 |
| **all 100 pages** | **15 / 49 / 36, 2,562 → 2,614** (word edits 898 → 924) |

R4d + R3f + A1 against Tesseract alone: 100 / 0 / 0, 11,885 → 2,614.

**Where R3f's 52 extra edits are.** Edits are counted by the class of the gold character (substitutions and deletions) or of the predicted character (insertions):

| Class | R3d edits | R3f edits | Change |
|---|---|---|---|
| Latin letters | 63 | 83 | +20 |
| Punctuation (mostly the ledger ` \| `) | 814 | 827 | +13 |
| Spaces and line breaks (mostly the ledger ` \| `) | 1,617 | 1,624 | +7 |
| Digits | 45 | 51 | +6 |
| Hebrew letters | 23 | 29 | +6 |

- **By script** (page CER; 932 Latin letters, 4,704 digits, 9,036 Hebrew letters in the reference): Latin 0.048 → 0.075, digits 0.008 → 0.009, Hebrew 0.002 → 0.003.
- **ASCII marks** (R3d kept every one):
  - hyphen 335 → 328 kept (7 deleted);
  - apostrophe 37 → 33 kept (one becomes `׳`);
  - quotation mark 33 → 28 kept (three become `״`, one `”`).
- R3f also adds 6 typographic marks where the gold has none: `״` 3, `׳` 1, `“` 1, `”` 1.
- **`ledger` with one cell per line** (raw NFC edits on the 20 pages, hocrgen#98): R3d 20, R3f 42. As is: 2,418 against 2,438.

### Reading (R3f)

- **R3f closes the typographic gap.**
  - On eval-typo-heldout, `primary.v1` goes from 0.041 / 0.166 to 0.010 / 0.044, and 75 of 80 pages improve (422 → 99 character edits).
  - R3f keeps 268 of the 308 new marks, where R3d kept none. It no longer adds stray ASCII hyphens or quotation marks (106 and 147 for R3d, 0 and 3 for R3f).
  - What remains:
    - geresh read as an apostrophe (17 of 58);
    - the right single quote, always read as an apostrophe (5 of 5);
    - en dashes read as em dashes (4 of 26).
- **On gold-like line crops, R3f matches R3d elsewhere.**
  - With Kraken polygons at height 1800 (e), the training geometry, seed-101 and held-out are unchanged.
  - With R4d + A1, seed-101 and held-out are unchanged too; both intervals include zero.
  - Hebrew-letter CER on eval-typo-heldout is unchanged at 0.004.
- **On batches without the new marks, R3f loses a little.**
  - eval-mixed-heldout: 0.016 → 0.021, mostly `handwritten_note_heavy_wear`.
  - eval-layout-heldout: 0.122 → 0.124. Part of that is ASCII `"` and `'` in the gold read as `״` and `׳`, and part is Latin letters (CER 0.048 → 0.075).
  - The fixture's gain (0.146 → 0.130) is mostly the em dash, and the fixture is a development set.
- **R3f is less robust than R3d to line crops unlike its training geometry.**
  - hocrsyngen's polygons (d) about double R3d's CER, almost all on `printed_letter_heavy_scan`.
  - Tesseract's rectangles are worse on every template.
  - R3d had narrowed this crop-style split over R3c (R3d section). R3f widens it again.
  - One guess, untested: the larger character set and the Latin text give the recognizer more wrong outputs to fall into on degraded crops.
- **Recipe or seed?** Each recognizer is one training run, with `--no-deterministic` on `mps`. The second R3f seed (s7202) is the check. It reuses the identical recipe and corpus on a fresh batch seed.
- **R3f stays far ahead of Tesseract** on eval-typo-heldout and eval-layout-heldout: 80 / 0 / 0 and 100 / 0 / 0 pages.

### Run identities (R3f)

| Part | Identity |
|---|---|
| Training batch | hocrsyngen `88ba5e6` (`s11b-ledger-fit-v1`), Pillow 13.0.0 with raqm. 3,000 pages, seed 7201, seven templates round robin (428–429 pages each). Corpus `7c2a62b83d3be29ab796c30b3e3272576c1f7e9c4302f7003fc6829f97984573` (S10b `hebrew_lines_train_v1.txt` `a3f2f0db…`, then S13a `hebrew_mixed_lines_train_v1.txt` `203df9e8…`, then S13b `hebrew_typographic_lines_train_v1.txt` `5c385b41…`). Manifest `e7406e20a6144f9128068dc5c6245947cd598f31bbb8ea71f89e05e9d6243f12`, line annotations `30cba05a8a7c5579e500069b850c44e29491612de1cf2ddb9e6ed19e2bd050a3`. Validates; quality check passes |
| Training | heocr-engine `660e5a4` `train-kraken`, R3d's settings: `--line-polygons kraken --polygonizer-height 1800`, Kraken 7.0.2, batch size 16, lr 0.001, augment, `quit early` lag 3, min-epochs 5; split by sample, seed 0, validation fraction 0.05. mps, seed 42, not deterministic. Record `run_r3e_s7201.record.json` (validates) |
| Model | `best_0.9960.safetensors`, sha256 `52a208659f06f771ce4aebb09fa3a6b737fc82c92e084165e4fca9c419107dfd`, 16,167,536 bytes; licence `Needs verification`, unpublished |
| Seed-101 and held-out rows | heocr-engine `660e5a4`; inference as R3d (Kraken 7.0.2 on cpu, `-f page ocr --reorder --base-dir R`, the same line inputs); hocrgen `2d3efb0`. Bootstrap: 2,000 page resamples, seed 0 |
| R4d + A1 rows | heocr-engine `660e5a4`, `kraken-python` stage on cpu, `--reading-order-classes region`; R4d `d32cd1a8…`, A1 `69aa1946…`. hocrgen `2d3efb0` for seed-101 and held-out, `c8fb74e` for the fixture and eval-mixed-heldout, as for the R3d rows. The polygonizer reports "failed on line 0" 4 times over the four batches; this is segmenter geometry, not the recognizer |
| R3f prediction sets, seed-101 | `blla -d horizontal-rl` `b32544412aeeec48…`, Tesseract lines `1ec22b4683d4370e…`, (e) `26df97ef380f6f75…`, (d) `8ebe342c0bdeacc4…`, R4d + A1 `7d925b17cf9d41a9…` |
| R3f prediction sets, held-out | `blla -d horizontal-rl` `b6891c0b2ed1808b…`, Tesseract lines `7bfcf2e479cf3b76…`, (e) `16f05c6b980013fc…`, (d) `932d30b3856f85d8…`, R4d + A1 `720593811345b998…` |
| R3f prediction sets, mixed batches (R4d + A1) | hocrgen fixture `be7a485c161cc0c7…`, eval-mixed-heldout `8ba6d250d35c1696…` |
| eval-typo-heldout | `tasks/eval-typo-heldout/eval-typo-heldout`: hocrsyngen `88ba5e6` (`s11b-ledger-fit-v1`), Pillow 13.0.0 with raqm, seed 9201, 80 pages. Packaged `hebrew_typographic_lines_eval_v1.txt` (`3364283592492d8827ae94b8899ce44cecedf1281b4fbeb69f9d76b3e9a09a3c`). Manifest `23019cf554472fb11432d96c4c5972caad8ff087fc8c99b961361d4f7205221c`, line annotations `7c493887c3def96e24b8e507a685b0ddbedf689b8d4353027389b2e148f628da`. Validates. Quality check: 640 lines, 4 occluded, no truncation |
| eval-layout-heldout | as in its section above (manifest `facbe571069308c8f842d4f30d0cd946c2494061bfa1018c900a556b551e2259`) |
| heocr-engine (R4a's batches) | R3d rows: `660e5a4`. R3f rows: `c5f8034` (main; the same code as `660e5a4`). Both use the `kraken-python` stage on cpu, from their own detached worktree |
| Models (R4a's batches) | R4d `d32cd1a8efe7354445ccfea76551cc9943ca05792c332b5865f9bec985fe7bf7`; R3d `374f9302eba092f67c06af0be2ef04c4ad528e4f60a11c2255a2bd3a75c0c889`; R3f `52a208659f06f771ce4aebb09fa3a6b737fc82c92e084165e4fca9c419107dfd` (`best_0.9960.safetensors`, record `run_r3e_s7201.record.json`, validated before scoring); A1 `69aa1946583bb68ddf13ef20860582f4aa982a46b2f79e38bd7d9ae20535fb56` (`--reading-order-classes region`) |
| Tesseract | 5.5.3, `heb+eng`, `--psm 3` |
| hocrgen | `c8fb74e` (main): `primary.v1`, `raw.v1`, `consonantal.v1`, `punct_folded.v1` |
| Per-character and per-class rows | R4a's `mark_table.py` and `edit_class.py` (local): `primary.v1` normalization, `rapidfuzz` 3.14.6 `Levenshtein.editops` per page |
| Prediction sets (R4a's batches) | eval-typo-heldout: Tesseract `aa9fe9127d127265…`, R3d `922c8a9fed7f17db…`, R3f `848bb222f8b5833d…`. eval-layout-heldout: R3d `beca6e735a13326c…`, R3f `22ac660f18381a0e…` |
| Run (R4a's batches) | every set complete (80 and 100 pages), no failures. On eval-layout-heldout the polygonizer reports "failed on line 0" once, as it did for R3d. One kraken job of R4a's at a time, next to R4b's scorer |

Limits:
- One training run per recognizer, and one seed per batch. The paired intervals cover page sampling only, not training-run variation, which is what the s7202 seed is for. R4a's eval-typo-heldout and eval-layout-heldout rows have no intervals.
- The per-character rows depend on a page-level alignment: a substitute is whatever the optimal alignment pairs with the gold mark.
- Every batch shares the generator and fonts with R3f's training batch. eval-typo-heldout shares none of its text lines.
- Gold that uses ASCII `"` and `'` (seed-101, held-out, eval-mixed-heldout, eval-layout-heldout) counts a typographically correct `״` or `׳` as an error.
- The hocrgen fixture is a development set for reading order, and its gain here is mostly one character (`—`).
- Predictions, line files and reports stay local.

### R3f second seed (s7202) (2026-11-05)

The second R3f run reuses R3f's recipe, corpus and engine exactly. Only the training batch seed changes, from 7201 to 7202; the training seed is again 42. Its local run name keeps the working label: `run_r3e_s7202`. No page of the s7202 batch matches seed-101, held-out, the hocrgen fixture, eval-mixed-heldout, eval-layout-heldout or eval-typo-heldout, by page image sha256 or by page text.

**Training:**
- **Stopping:** early stopping after 9 epochs. The best epoch is 5 (0-based), with val_accuracy 0.9959 on its own validation split.
- **Split:** train 2,850 pages / 47,705 lines, validation 150 pages / 2,645 lines; every template is in both.
- **Lines:** the polygonizer drops 2 lines, both in the training split.
- **Pause:** the run was paused (SIGSTOP) from 13:15 to 21:46 IST on 2026-11-04 because the laptop was on battery, then resumed. The record validates.

**`primary.v1` CER, R3d, R3f s7201 and R3f s7202.** These are the same line sources and pipeline as the R3f rows above. Intervals are 95% paired page bootstrap intervals (2,000 resamples, seed 0) on the change in pooled CER. Pages are improved / unchanged / worsened.

| Batch, lines | R3d | R3f s7201 | R3f s7202 | s7202 against R3d | s7202 against s7201 |
|---|---|---|---|---|---|
| seed-101, (d) | **0.028** | 0.054 | 0.048 | 14 / 19 / 47 [+0.012, +0.029] | 33 / 15 / 32 [−0.012, +0.000] |
| held-out, (d) | **0.024** | 0.064 | 0.053 | 16 / 14 / 50 [+0.018, +0.042] | 38 / 9 / 33 [−0.021, −0.003] |
| seed-101, Tesseract lines | **0.194** | 0.216 | 0.226 | 15 / 7 / 58 [+0.022, +0.040] | 32 / 3 / 45 [+0.003, +0.017] |
| held-out, Tesseract lines | **0.196** | 0.248 | 0.256 | 15 / 5 / 60 [+0.041, +0.083] | 39 / 11 / 30 [−0.002, +0.021] |
| seed-101, R4d + A1 | **0.019** | 0.018 | 0.023 | 25 / 23 / 32 [+0.001, +0.006] | 19 / 25 / 36 [+0.002, +0.007] |
| held-out, R4d + A1 | **0.009** | 0.010 | 0.011 | 21 / 35 / 24 [−0.002, +0.006] | 21 / 40 / 19 [−0.002, +0.004] |
| hocrgen fixture (development set), R4d + A1 | 0.146 | 0.130 | **0.128** | 93 / 1 / 6 [−0.022, −0.015] | 39 / 31 / 30 [−0.004, +0.000] |
| eval-mixed-heldout, R4d + A1 | **0.016** | 0.021 | **0.016** | 28 / 30 / 22 [−0.003, +0.002] | 32 / 32 / 16 [−0.010, −0.002] |

**Replicated in both seeds (a recipe effect):**
- **Line crops unlike the training geometry regress.**
  - (d): both seeds regress, again almost all on `printed_letter_heavy_scan`. s7202 goes 0.043 → 0.102 on seed-101 and 0.038 → 0.120 on held-out.
  - Tesseract lines: both seeds regress on every template.
- **The fixture gain holds.** It is again mostly the em dash: s7202 writes 312 `—`, where s7201 wrote 317 and R3d none. The fixture remains a development set.

**Seed variance (not replicated):**
- **The eval-mixed-heldout loss.** s7202 is level with R3d (0.016 → 0.016, interval includes zero), where s7201 lost 0.016 → 0.021.
- **`handwritten_note_heavy_wear`** goes 0.025 → 0.028, where s7201 went to 0.041.

**s7202 only (unreplicated):**
- **Seed-101 with R4d + A1** dips 0.019 → 0.023, mostly on `printed_letter` (0.021 → 0.031).
- **s7201 was level with R3d there** (0.019 → 0.018). One seed shows it and the other does not, so it is not attributed to the recipe.

**Decision (maintainer's lead, 2026-11-05):**
- R3d stays the default and reported recognizer. R3f stays a typographic-punctuation candidate.
- The reason, corrected after the second seed: R3f's regression on degraded crops and on line geometry outside its training (d, Tesseract lines) is a recipe effect, seen in both seeds. The eval-mixed-heldout loss was seed variance.

**Run identities (R3f s7202):**

| Part | Identity |
|---|---|
| Training batch | hocrsyngen `88ba5e6` (`s11b-ledger-fit-v1`), Pillow 13.0.0 with raqm, 3,000 pages, seed 7202. The seven templates round robin, 428–429 pages each. Corpus `7c2a62b83d3be29ab796c30b3e3272576c1f7e9c4302f7003fc6829f97984573`, as for s7201. Manifest `7853eb5ae46e54e7e33ef3fb83bd01eb450f1b3253f6e992f554bce1b1d867a3`, line annotations `b07a11f29227c212dce8f2003b7347f73ce74114062bb2cc194db43274787686`. Validates; quality check passes (50,352 lines) |
| Training | heocr-engine `660e5a4` `train-kraken`, the s7201 command with the s7202 batch: Kraken 7.0.2, mps, seed 42, not deterministic. Record `run_r3e_s7202.record.json` (validates) |
| Model | `best_0.9959.safetensors`, sha256 `88f60b38348514a9a2d4e1bba2af8412b5488bd0a1c4813f8577b82181e20406`, 16,167,536 bytes. Licence `Needs verification`, unpublished |
| Scoring | As for the s7201 rows: heocr-engine `660e5a4`; hocrgen `2d3efb0` for seed-101 and held-out, `c8fb74e` for the fixture and eval-mixed-heldout; R4d `d32cd1a8…`, A1 `69aa1946…` with `--reading-order-classes region`. The record is validated and the model sha checked before scoring. The polygonizer reports "failed on line 0" 4 times over the four R4d batches, as for s7201 |
| Prediction sets, seed-101 | (d) `0f230fa5f3d9dea2…`, Tesseract lines `58b6d8c878016411…`, R4d + A1 `849d5898a4669bb5…` |
| Prediction sets, held-out | (d) `c772310bfe7d6448…`, Tesseract lines `1adbed947f5f3a25…`, R4d + A1 `fd4227e7615f8008…` |
| Prediction sets, mixed batches (R4d + A1) | hocrgen fixture `c6adabfaf135e828…`, eval-mixed-heldout `0528f762a4a58eb7…` |

Limits:
- Two seeds of one recipe, each one non-deterministic run on `mps`, is still a small sample of training-run variation.
- s7202 was not scored on eval-typo-heldout, eval-layout-heldout, or with `blla` or (e) lines.
- Predictions, line files and reports stay local.
