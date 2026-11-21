# Baselines

> Reported figures are from registered held-out real pages. Project benchmarks: https://heocr.github.io/benchmarks.html

Both baselines run locally with user-supplied engines and models. Nothing is downloaded, and each prediction records executable and model hashes. The hashes help with provenance but do not guarantee identical results across machines or library versions. Neither baseline comes with an accuracy claim. HeOCR uses the pinned hocrgen scorer and human-adjudicated references for the real-page results below. Generated examples, pseudo-labels and silver text inform development and selection. See [the scored-set decision](../planning/decisions/0012-real-page-scored-sets.md).

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
  - **Why the order is recomputed here:** Kraken 7.0.2 does not deliver a usable learned order. `kraken … ocr` writes plain text in the heuristic order even when a reading-order model is attached. The deprecated `blla.segment` stores the learned order in `line_orders` as indices into its line list *before* the heuristic sort, next to the sorted lines, so reading the returned lines by those indices gives the heuristic order back. `tests/test_kraken_api.py` (`KrakenLineOrdersBugTests`) proves this against Kraken's own code. The stage keeps the pre-sort list Kraken hands its heuristic order function, runs the reading-order model on that list, and maps the result onto the returned lines by line id. It fails closed unless the result is a permutation. Reported upstream as [mittagessen/kraken#820](https://github.com/mittagessen/kraken/issues/820) (2026-11-06).
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
- **Known issue, Kraken 7.0.2 on macOS:** Kraken occasionally crashes on exit after it has written its output (stderr shows `libc++abi` … `recursive_mutex lock failed`) and exits non-zero. The wrapper treats a nonzero exit as a failed run.

Reference models, verified 2026-11-01 and recorded in [decision 0006](../planning/decisions/0006-model-licences.md). Pin runs by model sha256 and version DOI, never by concept DOI:

| Model | Version DOI | Licence | sha256 |
|---|---|---|---|
| `blla.mlmodel` (baseline segmentation, 2025-01-06) | 10.5281/zenodo.14602569 | Apache-2.0 | `77a638a83c9e535620827a09e410ed36391e9e8e8126d5796a0f15b978186056` |
| `BiblIA_01.mlmodel` (medieval Hebrew bookhand) | 10.5281/zenodo.5468286 | CC-BY-SA-4.0 | `bb48c481d8c46b41465920482e253dc990163405c584d24700cfb0d9b4ca9147` |

Attribution: BiblIA_01, Medieval Hebrew manuscripts version 1.0, by Daniel Stökl Ben Ezra, licensed CC BY-SA 4.0, doi:10.5281/zenodo.5468286. heocr-engine does not redistribute either model. 
**Needs verification:** whether CC BY-SA 4.0's ShareAlike reaches predictions (output text) made with BiblIA_01 is unresolved, and no claim is made either way. Until it is settled, predictions made with BiblIA_01 that HeOCR publishes or commits carry the attribution above, and their licence is left to the maintainer's decision.

The stage record's `license: "Apache-2.0"` describes the Kraken engine only. Model licences follow from the `model:segmentation` and `model:recognition` hashes in `artifacts`, matched against the table above, not from that field.

BiblIA_01 was trained on medieval manuscripts. On modern cursive it recognizes little. In a local smoke run on a public-domain 1892 manuscript page it produced only scattered characters. Treat it as a floor and a check that the pipeline works, not as a target. The segmentation concept DOI (10.5281/zenodo.14602568) resolves to its newest version, so it does not identify a model.

## Development configurations

Earlier development work used template-rendered pages for recognizer training and line-order checks. The recognizer experiments compared font and real-glyph rendering, Hebrew/Latin text mixtures, typographic punctuation, and crops from sidecars and Kraken geometry. The segmenter experiments used line polygons and region classes to train reading order. For configurations without a registered real-world evaluation, the status is **not measured on a held-out set yet**.

## R3i: real-glyph synthetic pages, fine-tuned from R3h (2026-11-08)

**Status: ablation diagnostic (decision 0012 rule 3).** E2d3d (`e2d3d_wikisource_printed_v5`, human-adjudicated) is a scored set. These rows compare three fine-tunes on it to answer a data question. No arm, checkpoint or setting is selected for release from them, and none of the three models is the recognizer of record. R3h stays the recognizer of record.

**Question:** at an equal line budget and equal epochs, do hocrsyngen's real-glyph book pages (`compose-glyph-pages`, glyphs harvested from scanned Wikisource books) lower the recognizer's error on real scanned printed Hebrew more than font-rendered book pages do?

**Design:**
- Each arm fine-tunes R3h (decision 0013, `--resize union`) for exactly 4 epochs at lr 1e-4, with R3h's recipe otherwise.
- The three arms differ only in their training pages, each about 25,000 lines:
  - **A:** font-rendered hocrsyngen book pages only.
  - **B:** real-glyph pages only.
  - **C:** half and half.
- All pages render the same text, so glyph realism is the only difference between A and B.
- Segmentation is held fixed. Each model re-recognises saved line geometry of the 38 pages for three line sources:
  - R4d + A1, the released pipeline;
  - Tesseract psm 3 lines;
  - `blla`.
- **Checkpoints:** each arm's `best` is chosen on its own synthetic validation split. In all three it is the last epoch, so E2d3d plays no part in selection.

**Leakage and the headline set:**
- The glyph bank (`pgb-v1`) was harvested from Wikisource Indexes registered in hocrgen's `synthetic_training_works.yaml`. The scored pages themselves were excluded from harvesting, but 28 of the 38 E2d3d pages come from Indexes that gave the bank glyphs from their other pages.
- **The headline is the other 10 pages (6 Indexes)**, whose books gave the bank nothing.
- The other pages share books with the glyph bank and are excluded from the reported comparison.

### Headline: the 10 bank-disjoint pages (`primary.v1` CER / WER)

| Line source | R3h | A (font) | B (real glyph) | C (mix) |
|---|---|---|---|---|
| R4d + A1 | 0.853 / 1.083 | 0.850 / 1.076 | 0.836 / 1.023 | 0.837 / 1.039 |
| Tesseract lines | 0.547 / 0.848 | 0.494 / 0.796 | 0.457 / 0.614 | **0.445** / 0.624 |
| `blla` | 0.656 / 0.987 | 0.597 / 0.916 | 0.568 / 0.816 | 0.567 / 0.813 |

Tesseract alone scores 0.385 / 0.596 on these 10 pages.

**Paired deltas on the 10 pages.** Each cell is the CER delta with its 95% page interval, then its Wikisource-Index cluster interval (6 clusters). 2000 resamples, seed 20261106.

| Line source | B − A | C − A | C − B |
|---|---|---|---|
| R4d + A1 | −0.014 [−0.033, −0.006]; cl [−0.054, −0.008] | −0.013 [−0.030, −0.006]; cl [−0.045, −0.006] | +0.001 [−0.003, +0.006]; cl [−0.004, +0.011] |
| Tesseract lines | −0.037 [−0.087, −0.006]; cl [−0.137, −0.013] | −0.049 [−0.084, −0.027]; cl [−0.120, −0.033] | −0.012 [−0.022, +0.003]; cl [−0.021, +0.020] |
| `blla` | −0.029 [−0.072, −0.008]; cl [−0.126, −0.011] | −0.030 [−0.058, −0.013]; cl [−0.099, −0.019] | −0.000 [−0.012, +0.022]; cl [−0.009, +0.027] |

WER moves more than CER:
- B − A on Tesseract lines: −0.183 [−0.289, −0.077].
- B − A on `blla`: −0.100 [−0.177, −0.048].

Fine-tuning on font pages also helps on its own. A − R3h on Tesseract lines is −0.053 [−0.088, −0.007], and on `blla` −0.058 [−0.092, −0.004]. On R4d + A1 it is −0.003 [−0.021, +0.012].

## R3j, R5 and R6: release-candidate recognizers scored once on real pages (2026-11-09)

**Status: scored once under decision 0012 rule 3.** Each model's checkpoint was chosen before any E2d3d scoring: R3j and R5 on their own synthetic validation splits, R6 on two held-out real NLI records. E2d3d informed no choice of checkpoint or setting. These rows record results. They do not change the recognizer of record: R3h stays the Kraken recognizer of record, and any release decision is the maintainer's.

**Models:**
- **R3j** (Kraken): fine-tunes R3h (decision 0013) on 50,000 lines with R3i's recipe. Its real-glyph bank (`pgb-v2.1`) shares no Wikisource Index with E2d3d, so the 10 pages vs 38 pages split matters less here than it did for R3i. There are two arms:
  - **mix21:** 25,011 real-glyph lines (bank `pgb-v2.1`: 5 Ben-Yehuda × NLI faces, every evaluation Index excluded) plus 25,067 font-rendered lines.
  - **font:** 50,013 font-rendered lines, as a control.
- **R5** (Tesseract): fine-tunes tessdata_best `heb` on R3j's mix21 lines, so it sees synthetic lines only.
- **R6** (Tesseract): fine-tunes tessdata_best `heb` on **real scanned lines**. These are the 13,648 train lines of `bynli_lines_v1`, cut from NLI scans of public-domain books, each labelled with the Ben-Yehuda edition text that the alignment placed on the line, never with OCR output.

**Scoring:**
- Every page goes through Tesseract psm 3. R3j re-recognises the saved Tesseract psm 3 line geometry of each page, as R3i did.
- All rows use hocrgen `d4a3414` `evaluate-references` with `primary.v1`, the same pinned scorer as R3i.
- Intervals are paired against stock Tesseract (brew `heb`): first the 95% page interval, then the Wikisource-Index cluster interval (14 clusters on 38 pages, 6 on the 10). Both use 2000 resamples, seed 20261106.

### Headline: the audited references (`primary.v1`, Tesseract psm 3 lines)

The references are `e2d4c_wikisource_printed_v7`: the same 38 pages with the full E2d4c human audit (hocrgen#157, merged as `c21168f`; decisions file sha256 `fb78f146…`). The 10-page subset is R3i's bank-disjoint set.

| Engine | CER 38 / 10 | WER 38 / 10 | ΔCER vs stock, 38 (page; cluster) | ΔCER vs stock, 10 (page; cluster) |
|---|---|---|---|---|
| Stock Tesseract `heb` (brew) | 0.226 / 0.384 | 0.473 / 0.588 | — | — |
| tessdata_best `heb` | 0.225 / 0.376 | 0.481 / 0.609 | −0.001 [−0.006, +0.005]; cl [−0.008, +0.007] | −0.008 [−0.026, +0.004]; cl [−0.019, +0.003] |
| R5 (synthetic mix21 lines) | 0.239 / 0.416 | 0.473 / 0.660 | +0.013 [−0.003, +0.031]; cl [−0.010, +0.048] | +0.032 [+0.007, +0.067]; cl [+0.006, +0.095] |
| **R6 (real NLI lines)** | **0.209** / 0.383 | **0.407** / 0.585 | **−0.016 [−0.023, −0.010]; cl [−0.024, −0.005]** | −0.002 [−0.012, +0.012]; cl [−0.006, +0.002] |
| R3j mix21 (Kraken) | 0.261 / 0.479 | 0.539 / 0.723 | +0.036 [+0.017, +0.056]; cl [+0.008, +0.079] | +0.094 [+0.046, +0.146]; cl [+0.039, +0.165] |
| R3j font (Kraken) | 0.317 / 0.494 | 0.678 / 0.772 | +0.091 [+0.073, +0.111]; cl [+0.069, +0.123] | +0.109 [+0.061, +0.160]; cl [+0.055, +0.176] |

**R6 against tessdata_best, its base:**
- 38 pages: −0.015 [−0.024, −0.007]; cl [−0.026, +0.001].
- 10 pages: +0.007 [−0.006, +0.018]; cl [−0.005, +0.019].

**R6 against stock, page by page** (`primary.v1`, the 38 pages above; `reports_audit2/38/tess_r6_alone__vs__tesseract_alone.json`, `comparison.deltas.adjudicated_reference.profiles.primary.v1`): CER improves on 26 pages, is unchanged on 2 and worsens on 10. WER R6 − stock is −0.066 [−0.086, −0.046] (paired bootstrap).

**Audit caveat:** some E2d4c audit proposals were found where Tesseract and R3h agree with each other but not with the reference. The corrections may therefore lean slightly toward what Tesseract reads. The audit lowers stock Tesseract's CER from 0.237 to 0.226 on the 38 pages, and that drop is not an improvement in Tesseract. Compare engines paired on the same references, as the table does.

### Order-free check (R6)

The order-free check scores bags of characters, ignoring order (supplementary, not a hocrgen metric; R4f's `r4f_order_free.py`, `primary.v1` text). Its character-bag error counts a substitution twice and a misordering not at all:

| Engine | Pre-audit refs | Audited refs |
|---|---|---|
| R6 | 0.215 (CER 0.219) | 0.215 (CER 0.209) |
| Stock | 0.237 (CER 0.237) | 0.238 (CER 0.226) |

The bag error is about the same as CER, so almost none of R6's remaining error is reading order. It is recognition. R6 also emits about 7% fewer characters than the references (stock: about 3% fewer), so deletions are part of it.

### Reading (R3j, R5, R6)

**Verdict:** real scanned lines are what move Tesseract on real print. Synthetic lines do not.
- **R6 is the first trained model to beat stock Tesseract on the 38 adjudicated pages.**
  - CER falls from 0.226 to 0.209 and WER from 0.473 to 0.407, with page and cluster intervals excluding zero.
  - Against its own base (tessdata_best), the page interval excludes zero, but the cluster interval just reaches it (+0.001).
  - On the 10 bank-disjoint pages R6 is level with stock (−0.002 [−0.012, +0.012]). Stock's error is highest on those 10 pages, and almost all of R6's training lines come from three books.
- **R5 shows that synthetic lines do not transfer to real scans for Tesseract.** It trained on the same 50k mix21 lines as R3j, real-glyph included. It is slightly worse than its base on 38 pages and clearly worse on the 10 (+0.041 vs tessdata_best, page and cluster intervals above zero).
- **R3j: mix21 beats font on every line source and both sets**, so real-glyph pages help again with a bank that shares no Index with the scored pages.
  - Neither arm beats Tesseract alone: on Tesseract lines, mix21 scores 0.261 / 0.479 against stock's 0.226 / 0.384.
  - On the 10 pages R3j mix21 (0.478) is also behind R3i C (0.445). R3j differs from R3i C in bank, text and line budget, so this does not isolate a cause.
- **Segmentation still dominates the Kraken pipeline.** On R4d + A1 every recognizer stays above 0.83 CER.
- tessdata_best and brew's stock `heb` are level on the 38 pages.

**Implication for the data plan:**
- Grow the real line set: more books, and more varied prints, toward the hard 10.
- Use separate development records for selection. Keep E2d3d for evaluation.

Limits:
- **One training run per model.** The intervals cover page and Index sampling, not training seeds.
- **R6's dev records** (Silman, Brainin: 7,092 lines) are biased toward lines Tesseract reads reasonably. Their BCER compares models; it is not a level.
- **R6's training books:** five records, all NLI scans accepted as public-domain free use. 99.9% of the lines come from three of them:
  - Berashadsky: 6,076 lines;
  - Citron: 6,052;
  - Tchernowitz: 1,511.

  Frank adds 8 lines and Katzenelson *Shirim* 1. Two pointed prints (*Mahamadim*, Mandelkern) were dropped. *Shirim*, since classified as a pointed print, kept its one line with niqqud removed.
- **Overlap with E2d3d:** checked on 2026-11-10 for the R6 release (`release/r6/card_body.md`). The 13,648 training labels share no word 6-gram with the 38 reference texts. The full Ben-Yehuda texts of the five training books share three, all from two Bible verses that one Frank story and one evaluation page both quote, and none of them is in Frank's 8 training lines. The scans differ (NLI, not Wikisource), and no evaluation manifest names an NLI record. data-collection's later F8f3 search excludes such works.
- **Line sources:** R3j's rows re-recognise saved line geometry, and the Tesseract rows run full-page psm 3, so their segmentation differs.
- **The audited references** carry the Tesseract-agreement caveat above.
- **Publication.** Under decision 0014, R6 is released as `heocr_r6.traineddata` (version DOI [10.5281/zenodo.24109989](https://doi.org/10.5281/zenodo.24109989), Hugging Face `HeOCR/heocr-r6-tesseract-heb`; `release/r6/`). R3j and R5 are not released. Predictions, reports and line sets stay local.

### Run identities (R3j, R5, R6)

| Part | Identity |
|---|---|
| R3j training | heocr-engine `2df76ec` `train-kraken`, R3i's recipe (base R3h `best_0.9959`, sha256 `f76affa8…`; `--resize union`, lr 1e-4, 4 epochs, `--line-polygons mix`, `--mix-buckets kraken×6,sidecar,rect`), Kraken 7.0.2, mps |
| R3j data | Text: the decontaminated Ben-Yehuda public-domain corpus (heocr-synth-gen S16c `corpus.txt`, `d55da980…`). mix21: 47,699 train / 2,379 validation lines, generation manifest `a71cefe0…`, annotations `26075099…`, from S16c `rc_glyph_v21_50k` (glyph bank `pgb-v2.1`, local only) and `rc_font_50k`. font: 47,490 / 2,523 lines, manifest `0096c02f…`, annotations `614e769e…` |
| R3j models | Best checkpoint is epoch 3 in both arms (stopped by the epoch limit). mix21 `a22b64dbd00b19e37c33f5453eef23888064bc114138345c625306407df65232`. font `8d7d59058adc4de80fd93f365562b1d0d9e551a6e30f3c3fe1e7508a7def58ca` (0.9993). Licence `Needs verification`, unpublished |
| Tesseract base | tessdata_best `heb.traineddata` at tesseract-ocr/tessdata_best `e12c65a` (Apache-2.0), sha256 `dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5`. Build files from tesseract-ocr/langdata_lstm `07930fd` (Apache-2.0) |
| R5 | `lstmtraining --continue_from` the base on R3j's mix21 lines, cut by bbox + 6 px, with truth in Tesseract's LSTM order; 47,765 train / 2,313 validation lines. Selected `heb_0.042_11834_199100` (selected on synthetic validation). `heb.traineddata` sha256 `1d716f519e3393de1d721f2c5fb0aeab95f50410e7f12abd1c26ed843b5469f9`. Unpublished |
| R6 data | heocr-synth-gen S16c `bynli_lines_v1`, manifest sha256 `9b6adb42…`. Train: 13,648 lines from five records (Berashadsky 6,076, Citron 6,052, Tchernowitz 1,511, Frank 8, Katzenelson *Shirim* 1). Dev and selection: 7,092 lines from two whole held-out records (Silman 1929, Brainin 1928). Built with hocrgen's canvas→image fix (`fc1a524`, #152). Alignment score ≥ 0.9 and line-OCR agreement ≥ 0.7; flagged pointed prints dropped |
| R6 training | `lstmtraining --continue_from` the base, two arms of up to 100k iterations: the stored learning rate (`lrdef`), and `--learning_rate 0.0001 --reset_learning_rate`. Starter unicharset: base plus `־` and `–` |
| R6 selection | Lowest dev BCER (lstmeval) over every checkpoint of both arms. The selected checkpoint came from the default learning-rate arm. |
| R6 model | `heb.traineddata` sha256 `73eb18e03f8793dff9c03699db0845779f6b5db4897824bcd61787245ec66e10`; data-collection's aligner records it as `ocr_model: r6@73eb18e0` (hocrgen#155). Licence `Needs verification`, unpublished |
| Scoring | hocrgen `d4a3414` `evaluate-references`, `primary.v1`, modality printed, Tesseract 5.5.3 psm 3. References: `e2d4c_wikisource_printed_v7` (built from hocrgen#157 at `6c74426`, merged as `c21168f`, decisions sha256 `fb78f146…`) and `e2d3d_wikisource_printed_v5`, each with its 10-page bank-disjoint subset. Paired page and Wikisource-Index cluster bootstrap, 2000 resamples, seed 20261106 |

## R7: Tesseract fine-tuned on more real books, scored once on real pages (2026-11-11)

**Status: scored once under decision 0012 rule 3. Published under decision 0014** as `heocr_r7.traineddata`, version DOI [10.5281/zenodo.24126449](https://doi.org/10.5281/zenodo.24126449) (`release/r7/`).

- **Recipe:** R6's recipe and base, on more data.
  - Base: tessdata_best `heb` `e12c65a`, with R6's starter. R7 does not continue from R6.
  - Data: 95,151 train lines of `bynli_lines_v2` (manifest `53dd7f1a…`), from 7 NLI and 23 Internet Archive books, labelled with Ben-Yehuda edition text.
  - Filters: 69 lines that share a word 6-gram with dev, and 145 whose labels contain ׳, ״ or —.
- **Arms:** `lrdef` and `lr1e4`, each run to 200k iterations.
- **Selection:** on the dev set, which is 7,113 lines of whole held-out works.
  - Selected the lower learning-rate arm on the development set.
  - Model sha256 `95faab81…`.

R7 checkpoint selection used 7,092 development rows from two sources now reserved in line_verify. R7 and its verified descendants carry that exposure. Comparisons on those sources are selection-exposed.

**38 pages, `primary.v1`:** CER / WER, with R7 minus baseline as Δ [page interval]; cl [Wikisource-Index cluster interval].

| Baseline | CER: base → R7 | ΔCER | WER: base → R7 | ΔWER |
|---|---|---|---|---|
| Stock | 0.226 → 0.209 | −0.017 [−0.029, −0.006]; cl [−0.034, +0.006] | 0.473 → 0.393 | −0.080 [−0.107, −0.053]; cl [−0.120, −0.024] |
| tessdata_best | 0.225 → 0.209 | −0.016 [−0.030, −0.001]; cl [−0.035, +0.013] | 0.481 → 0.393 | −0.088 [−0.115, −0.060]; cl [−0.131, −0.029] |
| R6 | 0.209 → 0.209 | −0.001 [−0.007, +0.006]; cl [−0.009, +0.012] | 0.407 → 0.393 | −0.014 [−0.027, +0.000]; cl [−0.031, +0.009] |

**10 bank-disjoint pages:**

| Baseline | CER: base → R7 | ΔCER | ΔWER |
|---|---|---|---|
| Stock | 0.384 → 0.393 | +0.009 [−0.004, +0.025]; cl [−0.009, +0.020] | −0.020 [−0.047, −0.005] |
| R6 | 0.383 → 0.393 | +0.011 [−0.001, +0.019]; cl [−0.010, +0.021] | −0.016 [−0.046, +0.000] |

### Reading (R7)

- **Line recognition improved; page CER did not.**
  - On the 38 pages, R7 ties R6 on CER, and WER is slightly lower within the intervals.
  - With Indexes resampled as clusters, R7's CER gain over stock is no longer clear, though its WER gain still is.
- **Order-free word recall improves:** letters only, R7 misses 28.6% of the reference words, R6 30.2% and stock 33.3%. R7 also emits 2.2% fewer letters than R6, mostly on two small-type rabbinic pages (`ws_index_381649` p0011, p0012).
- **Correction to "Order-free check (R6)" above.**
  - That bag counts each substitution twice, so its closeness to CER does not show that ordering costs nothing.
  - The opposite bound, minimum bag edits, is not a measure of ordering either: confusions that cancel across a page (one כ→ב, one ב→כ) cost nothing in a bag.
  - How much page error is layout and reading order is open. It needs a line-aligned measure, which is a prerequisite for choosing R8's direction.
- **R8 candidates:**
  - That line-aligned measure.
  - Rabbinic and small-type books in training.
  - A unicharset with ׳ ״ — and niqqud.
  - The out_alt editions (hocrgen#169).
