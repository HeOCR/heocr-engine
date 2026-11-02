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
- The prediction has one `recognize` stage named `kraken`. Its artifacts are the executable, `model:segmentation` and `model:recognition` hashes.
- `words` is empty: Kraken's plain-text output has no word geometry.
- The default timeout is 600 seconds per call, up to a maximum of 3600, because CPU inference on a full page can be slow.
- In a pipeline config: `{"type": "kraken", "executable": "…", "segmentation_model": "…", "recognition_model": "…", "base_dir": "R"}`.
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
