# HeOCR R3h: Hebrew document line recognition (kraken)

R3h is a [kraken](https://kraken.re) 7 text recognition model for lines of modern Hebrew documents. It reads printed and handwriting-style lines, including digits, Latin letters and typographic punctuation. HeOCR trained it from scratch on synthetic pages only.

It is a research baseline, not a production transcriber. All of its evaluation is on synthetic pages; no reviewed evaluation on real scans exists yet.

| | |
|---|---|
| File | `best_0.9959.safetensors`, 16,167,536 bytes |
| sha256 | `f76affa84e29536aa1d41f89d3507183c104f1620ca953fdfa5dd4b7a00ba6be` |
| Model type | recognition (line-level, CTC) |
| Format | kraken safetensors; trained and tested with kraken / ketos 7.0.2 |
| Licence | Apache-2.0, Copyright (c) 2026 HeOCR maintainers (see LICENSE and NOTICE) |
| Code | [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine) |

## Architecture

R3h uses ketos 7.0.2's default recognition network, unchanged:

```
[1,120,0,1 Cr3,13,32 Do0.1,2 Mp2,2 Cr3,13,32 Do0.1,2 Mp2,2 Cr3,9,64 Do0.1,2 Mp2,2 Cr3,9,64 Do0.1,2 S1(1x0)1,3 Lbx200 Do0.1,2 Lbx200 Do0.1,2 Lbx200 Do]
```

Input lines are scaled to a height of 120 pixels, in greyscale. The model expects baseline segmentation (`seg_type: baselines`).

**Codec (117 symbols):**
- the 27 Hebrew letters, final forms included, with geresh `׳` and gershayim `״`;
- the digits `0–9` and the Latin letters `A–Z a–z`;
- space and ASCII punctuation: `! " % & ' ( ) + , - . / : ; ? @`;
- typographic punctuation: `– — ‘ ’ “ ” „ …`;
- the shekel sign `₪`.

There is no niqqud (vowel points) and no cantillation.

## Uses

- **Line recognition in a kraken baseline-segmentation pipeline,** for modern Hebrew documents: letters, notes, archive cards, ledgers, forms and notices, in print or handwriting-style fonts.
- **A research baseline** for Hebrew OCR: comparing segmenters, line geometries and later HeOCR models.

### Out of scope

- **Unsupervised transcription of real documents.** No reviewed real-page evaluation exists, and the scores below are on synthetic pages only.
- **Medieval, liturgical or other historical Hebrew scripts.**
- **Niqqud,** which is not in the codec.
- **Real handwriting.** "Handwriting-style" means one handwriting font, not human hands.
- **Documents that are not mainly Hebrew.**

## Transcription guidelines, normalization and transformations

- **Ground truth** is Unicode NFC text in logical order. Training reorders it to display order, kraken's convention, with a right-to-left base direction.
- **At inference,** run kraken with `--reorder --base-dir R` to get logical-order text back. Without it, the output is in display order.
- **Punctuation:** quotes, dashes and ellipses are typographic where the text used them. Gershayim `״` and geresh `׳` are distinct from ASCII `"` and `'`.
- **Digits and Latin words** keep their left-to-right order inside the logical-order line.

## How to get started with the model

With the kraken CLI (7.x) and a baseline segmenter. kraken's default `blla` is shown here:

```sh
kraken -i page.png page.txt segment -bl -d horizontal-rl ocr -m best_0.9959.safetensors --reorder --base-dir R
```

- `-d horizontal-rl` reads lines that share a row right to left.
- `--reorder --base-dir R` returns logical-order text.

From a checkout of heocr-engine (`pip install '.[kraken]'`), `heocr-engine kraken` runs the same steps and writes a prediction record that hocrgen can score. See the heocr-engine README.

**Note:** the evaluation below used HeOCR's own segmenter (R4d) with a learned reading order (A1). Those models are not part of this release. No figure is reported here for R3h with `blla`.

## Training details

### Training data

All synthetic. Nothing was scraped, and no real document or third-party text was used.

- **Pages:**
  - 3,000 pages from [hocrsyngen](https://github.com/HeOCR/hocrsyngen) at `88ba5e6`, seed 7201, over seven templates: archive card, faded archive card, handwritten note, worn handwritten note, ledger, printed letter and heavily scanned printed letter.
  - The split is 2,850 training pages (47,633 lines) and 150 validation pages (2,706 lines). It is assigned per page by hash.
- **Fonts:** Alef (2,143 pages) and Gveret Levin (857 pages), both SIL OFL 1.1. Credits are in NOTICE.
- **Text:**
  - The hocrsyngen corpora S10b, S13a and S13b (932,130 bytes; sha256 `7c2a62b8…`).
  - They are original text authored by AI agents (Claude Opus 5.5 sessions) for HeOCR, with no third-party text, and dedicated to the public domain under CC0 1.0.
  - The register is administrative letters, notes, archives, ledgers, forms and notices; procurement and technical text with Latin terms, digits and codes; and typeset prose with typographic punctuation.
- **Line geometry:**
  - Each line is cropped in one of three ways, chosen by hash:
    - 3/4 with kraken's polygonizer around the true baseline;
    - 1/8 with the generator's exact line polygon;
    - 1/8 with the polygon's bounding box, its height adjusted by a pad of −0.14 to approximate Tesseract line boxes.
  - The mix is meant to cover the line geometry of different segmenters.

### Training procedure and hyperparameters

- **Initialisation:** from scratch. No third-party weights were loaded.
- **Trainer:** ketos 7.0.2 through `heocr-engine train-kraken` (heocr-engine `55b0f7d`).
- **Optimiser and data:**
  - AdamW, learning rate 0.001, constant schedule;
  - batch size 16, padding 16, augmentation on.
- **Stopping:** early stopping with lag 3 (minimum 5 epochs). It stopped after 8 epochs; the best was epoch 4.
- **Validation:** character accuracy 0.9959, on its own validation split with the same geometry mix.
- **Run:** seed 42, on Apple `mps`. Not deterministic, and the bytes are not reproducible.

## Evaluation

### Testing data, factors and metrics

#### Testing data

- **Batches:** hocrsyngen batches rendered from evaluation corpora that are kept apart from the training text, with the same two fonts. None was trained or tuned on.
  - seed-101 (the long-running benchmark);
  - held-out;
  - eval-mixed-heldout (mixed Hebrew/Latin/digits);
  - eval-typo-heldout (typographic punctuation);
  - eval-layout-heldout (layouts outside the training templates).
- **hocrgen fixture:** hocrgen's fixture batch, a development set.
- **Gold:** all gold is synthetic.

#### Metrics

The metric is CER under hocrgen's `primary.v1` normalisation profile, pooled over the pages of each batch. Each row varies the lines the recognizer is given:

- **true line polygons:** the generator's exact polygons;
- **Tesseract lines:** line boxes from Tesseract;
- **R4d + A1:** HeOCR's unreleased segmenter and reading order.

| Batch | Lines | CER |
|---|---|---|
| seed-101 | true line polygons | 0.014 |
| held-out | true line polygons | 0.004 |
| seed-101 | Tesseract lines | 0.116 |
| held-out | Tesseract lines | 0.088 |
| seed-101 | R4d + A1 | 0.020 |
| held-out | R4d + A1 | 0.010 |
| eval-mixed-heldout | R4d + A1 | 0.017 |
| eval-typo-heldout | R4d + A1 | 0.009 (269 of 308 typographic marks kept) |
| eval-layout-heldout | R4d + A1 | 0.124 |
| hocrgen fixture (development set) | R4d + A1 | 0.130 |

- This is one training run. The paired intervals in heocr-engine's `docs/baselines.md` (R3h section) resample pages, not training runs.
- A second training seed of an earlier model moved eval-mixed-heldout by about 0.005.

## Bias, risks and limitations

- **The synthetic gap.** The evaluation pages use the same two fonts and the same kinds of degradation as training. These scores overstate accuracy on real scans, possibly by a wide margin.
- **Ledgers:** most errors on eval-layout-heldout, 2,432 of 2,611 edits, are on ledger pages.
- **Worn handwriting-style notes:** on eval-layout-heldout, errors rose from 37 to 60 edits against the previous model (R3d). Latin letters account for most of the rise.
- **Gershayim:** `״` is sometimes written as ASCII `"`. There were 8 substitutions on eval-typo-heldout, plus 11 `"` inserted where the gold has none.
- **Rare typographic marks:** the right single quote was kept 0 of 5 times, and the en dash 20 of 26.
- **Printed letters (seed-101, R4d + A1):** slightly behind an earlier HeOCR model.
- **Script and language coverage:** modern Hebrew with some Latin only. No niqqud, and no historical hands.

## Licence and attribution

- **Licence:** Apache-2.0. Copyright (c) 2026 HeOCR maintainers.
- **NOTICE:** redistributions must keep the NOTICE file. It credits:
  - kraken (Apache-2.0);
  - the fonts Alef (HaGilda & Mushon Zer-Aviv, OFL-1.1) and Gveret Levin (The Gveret Levin Project Authors, OFL-1.1);
  - the CC0 synthetic training text.
- **Fonts:** the model contains no font data, and the fonts are not distributed with it.

## Provenance and reproduction

| Part | Identity |
|---|---|
| Training batch | hocrsyngen `88ba5e6`, seed 7201; manifest `e7406e20a6144f9128068dc5c6245947cd598f31bbb8ea71f89e05e9d6243f12`; line annotations `30cba05a8a7c5579e500069b850c44e29491612de1cf2ddb9e6ed19e2bd050a3` |
| Training text | `7c2a62b83d3be29ab796c30b3e3272576c1f7e9c4302f7003fc6829f97984573`, the concatenation of hocrsyngen `hebrew_lines_train_v1.txt`, `hebrew_mixed_lines_train_v1.txt` and `hebrew_typographic_lines_train_v1.txt` |
| Split | per page by hash, 5% validation; assignment `ade60b77ed8ecd23f67cf9876bd85c01db8ac589f8d709a6533eb9960c36cc20` |
| Training code | heocr-engine `55b0f7d`, ketos and kraken 7.0.2 |
| Training record | `r3h_training_run.json` (`heocr_engine_training_run.v1`), in this deposit |
| Scoring | hocrgen `2d3efb0` (seed-101, held-out) and `c8fb74e` (other batches); heocr-engine `55b0f7d` |

## Contact

Report problems and questions as issues on [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine/issues).

## Citation

Cite this model by its version DOI. <!-- DRAFT: add the version DOI after the deposit. Never cite the concept DOI. -->
