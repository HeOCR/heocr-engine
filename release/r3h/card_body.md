# HeOCR R3h: Hebrew document line recognition (kraken)

**Publication status.** This model is unpublished. HeOCR will release models or an OCR pipeline after a registered real held-out comparison shows that it beats the state of the art on at least one document type.

R3h is a [kraken](https://kraken.re) text recognition model for lines of modern Hebrew documents. It reads printed and handwriting-style lines, including digits, Latin letters and typographic punctuation. HeOCR trained it from scratch on synthetic pages only.

R3h is the recognition step of HeOCR's three-model pipeline:
- **R4d** finds the lines (segmentation);
- **A1** puts them in reading order;
- **R3h** reads them.

The three models are designed to work together (see [The pipeline](#the-pipeline)).

It is a research baseline, not a production transcriber. All of its evaluation is on synthetic pages; no reviewed evaluation on real scans exists yet.

**Performance: not measured on a held-out set yet.** HeOCR reports accuracy only on held-out sets, and this model has not yet been scored on one. No held-out score yet; HeOCR will score it once in a registered held-out run. That comparison will inform the publication decision.

- **How it was chosen:** training kept the epoch with the best character accuracy on its own validation pages (see [Training procedure](#training-procedure-and-hyperparameters)). The pipeline was then compared with kraken's default segmenter on synthetic development batches. These sets were used to choose and compare it, so they are not reported here as its performance.

| | |
|---|---|
| File | `heocr-r3h-recognition.safetensors` (trained as `best_0.9959.safetensors`), 16,167,536 bytes |
| sha256 | `f76affa84e29536aa1d41f89d3507183c104f1620ca953fdfa5dd4b7a00ba6be` |
| Model type | recognition (line-level, CTC) |
| Format | kraken safetensors; trained and tested with kraken / ketos 7.0.2 |
| Licence | Apache-2.0, Copyright (c) 2026 HeOCR maintainers (see LICENSE and NOTICE) |
| Training record | `r3h_training_run.json` (`heocr_engine_training_run.v1`) |
| Code | [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine) |

## The pipeline

| Step | Model | Record |
|---|---|---|
| Segmentation: baselines, line polygons, typed regions | R4d, `heocr-r4d-segmentation.safetensors` (`d32cd1a8…`) | `10.5281/zenodo.24023069` |
| Reading order: line order from each line's region type | A1, `heocr-a1-reading-order.safetensors` (`69aa1946…`) | `10.5281/zenodo.24023071` |
| Recognition | R3h, this model | `10.5281/zenodo.24372341` |

> **A1 needs heocr-engine.** kraken 7.0.2 cannot run A1 by itself, for two reasons:
> - its neural reading order passes the segmenter's line types to A1, while A1 was trained on region types. kraken rejects the class-mapping mismatch;
> - its text output ignores a learned line order ([mittagessen/kraken#820](https://github.com/mittagessen/kraken/issues/820)).
>
> Run the whole pipeline from a [heocr-engine](https://github.com/HeOCR/heocr-engine) checkout (`pip install '.[kraken]'`):
>
> ```sh
> heocr-engine kraken --api python --segmentation-model heocr-r4d-segmentation.safetensors --reading-order-model heocr-a1-reading-order.safetensors --reading-order-classes region --recognition-model heocr-r3h-recognition.safetensors page.jpg page.json
> ```

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

- **Line recognition for modern Hebrew documents:** letters, notes, archive cards, ledgers, forms and notices, in print or handwriting-style fonts. It is best used in the R4d + A1 pipeline.
- **A research baseline** for Hebrew OCR: comparing segmenters, line geometries and later HeOCR models.

### Out of scope

- **Unsupervised transcription of real documents.** No reviewed real-page evaluation exists, and all evaluation is synthetic.
- **Medieval, liturgical or other historical Hebrew scripts.**
- **Niqqud,** which is not in the codec.
- **Real handwriting.** "Handwriting-style" means one handwriting font, not human hands.
- **Documents that are not mainly Hebrew.**

## Transcription guidelines, normalization and transformations

- **Ground truth** is Unicode NFC text in logical order. Training reorders it to display order, kraken's convention, with a right-to-left base direction.
- **At inference,** run kraken with `--reorder --base-dir R` to get logical-order text back. Without it, the output is in display order.
- **Punctuation:** quotes, dashes and ellipses are typographic where the text used them. Gershayim `״` and geresh `׳` are distinct from ASCII `"` and `'`.
- **Digits and Latin words** keep their left-to-right order inside the logical-order line.

## Local use with an authorized copy

**The full pipeline (R4d + A1 + R3h).** This is the configuration HeOCR compared. A1's order is applied by heocr-engine's in-process kraken stage. In a checkout of [heocr-engine](https://github.com/HeOCR/heocr-engine), run `pip install '.[kraken]'`, then:

```sh
heocr-engine kraken --api python \
  --segmentation-model heocr-r4d-segmentation.safetensors \
  --reading-order-model heocr-a1-reading-order.safetensors --reading-order-classes region \
  --recognition-model heocr-r3h-recognition.safetensors \
  page.jpg page.json
```

- `page.json` is a prediction record. Its `text` holds the page in logical order, one line per row.
- Tested end to end with kraken 7.0.2 on CPU (about 8 s for one development page, from seed-101). The text matched the recorded prediction for that page exactly.

**kraken alone.** Kraken 7.0.2 cannot use A1:
- A1's classes are region types, and kraken's own pipeline gives it the segmenter's line types instead, so kraken rejects the pair.
- kraken's text output also ignores a learned line order ([mittagessen/kraken#820](https://github.com/mittagessen/kraken/issues/820)).

With kraken alone, R4d + R3h runs in kraken's heuristic line order. No figure is reported here for that configuration.

```sh
kraken -i page.jpg page.txt segment -bl -d horizontal-rl -i heocr-r4d-segmentation.safetensors \
  ocr -m heocr-r3h-recognition.safetensors --reorder --base-dir R
```

- `-d horizontal-rl` reads lines that share a row right to left.
- `--reorder --base-dir R` returns logical-order text.
- With `segment -bl` and no `-i`, kraken uses its default `blla` segmenter instead (see below).
- kraken 7.0.2 sometimes aborts on exit ("recursive_mutex lock failed") after writing its output. Retrying works.

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
- **Selection:** the epoch with the highest character accuracy on its 150 validation pages, with the same geometry mix, epoch 4. These pages chose the checkpoint, so their scores are not reported as performance.
- **Run:** seed 42, on Apple `mps`. Not deterministic, and the bytes are not reproducible.

## Evaluation

**Not measured on a held-out set yet.** HeOCR reports a model's accuracy only on sets held out from its training, selection and tuning. No held-out score yet; HeOCR will score it once in a registered held-out run.

- **Development sets, not reported as performance.** HeOCR compared the pipeline on six synthetic hocrsyngen batches: seed-101, a long-running benchmark read across rounds; the batches named held-out, eval-mixed-heldout, eval-typo-heldout and eval-layout-heldout, which were kept out of the training text but are not registered and were read during the rounds; and hocrgen's fixture batch, on which A1's design was tuned. Despite some of their names, none is a registered held-out set, so their figures are not given here. They are named in heocr-engine's `docs/baselines.md`.
- **All evaluation is synthetic.** No reviewed real-page evaluation exists.
- **Next:** a registered held-out run of the R4d + A1 + R3h pipeline, with kraken's default segmenter `blla` beside it and read the same way. That comparison will inform the publication decision.

## Bias, risks and limitations

- **The synthetic gap.** The development pages use the same two fonts and the same kinds of degradation as training. Real scans will likely do worse, possibly by a wide margin.
- **Ledgers on eval-layout-heldout:**
  - Most of that batch's error is on ledger pages.
  - Most of that is a gold convention, not misreading. hocrgen's ledger gold joins a row's cells with ` | `, while the pipeline reads one cell per line ([HeOCR/hocrgen#98](https://github.com/HeOCR/hocrgen/issues/98)). hocrgen#99 later added a per-cell reference view; the development comparison used the default view at `c8fb74e`.
- **Worn handwriting-style notes:** on eval-layout-heldout, errors rose against the previous model (R3d). Latin letters account for most of the rise.
- **Gershayim:** `״` is sometimes written as ASCII `"`, and `"` is sometimes inserted where the gold has none.
- **Rare typographic marks:** the right single quote is often lost, and the en dash sometimes.
- **One training run.** It was trained once, with one seed; how much another run would differ is not known.
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
| Training record | `r3h_training_run.json` (`heocr_engine_training_run.v1`), in this directory |
| Development scoring | hocrgen `2d3efb0` (seed-101, held-out) and `c8fb74e` (other batches); heocr-engine `55b0f7d` (R4d + A1) and `6f6df8b` (`blla`) |

## Contact

Report problems and questions as issues on [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine/issues).

## Archive reference

Former Zenodo version DOI: `10.5281/zenodo.24372341`.
