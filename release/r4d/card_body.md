# HeOCR R4d: Hebrew document baseline segmentation (kraken)

R4d is a [kraken](https://kraken.re) baseline segmentation model for pages of modern Hebrew documents. It finds:
- each text line's baseline, with a `stamp` line type for lines inside stamps;
- the line polygons;
- eight region types: title, body, stamp, signature, footer, margin, identifier and table cells.

HeOCR trained it from scratch on synthetic pages only.

R4d is the segmentation step of HeOCR's three-model pipeline:
- **R4d** finds the lines;
- **A1** puts them in reading order;
- **R3h** reads them.

The three are released together, as separate records that link to each other (see [The pipeline](#the-pipeline)).

It is a research baseline. All of its evaluation is on synthetic pages; no reviewed evaluation on real scans exists yet.

| | |
|---|---|
| File | `heocr-r4d-segmentation.safetensors` (trained as `best_0.8618.safetensors`), 5,056,800 bytes |
| sha256 | `d32cd1a8efe7354445ccfea76551cc9943ca05792c332b5865f9bec985fe7bf7` |
| Model type | segmentation (baselines and regions) |
| Format | kraken safetensors; trained and tested with kraken / ketos 7.0.2 |
| Licence | Apache-2.0, Copyright (c) 2026 HeOCR maintainers (see LICENSE and NOTICE) |
| Training record | `r4d_training_run.json` (`heocr_engine_training_run.v1`) |
| Code | [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine) |

## The pipeline

| Step | Model | Record |
|---|---|---|
| Segmentation: baselines, line polygons, typed regions | R4d, this model | <!-- DRAFT: R4d's reserved version DOI (release/README.md, plan step 2) --> |
| Reading order: line order from each line's region type | A1, `heocr-a1-reading-order.safetensors` (`69aa1946…`) | <!-- DRAFT: A1's reserved version DOI (release/README.md, plan step 2) --> |
| Recognition | R3h, `heocr-r3h-recognition.safetensors` (`f76affa8…`) | <!-- DRAFT: R3h's reserved version DOI (release/README.md, plan step 2) --> |

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

R4d uses ketos 7.0.2's default segmentation network, passed explicitly and otherwise unchanged:

```
[1,1800,0,3 Cr7,7,64,2,2 Gn32 Cr3,3,128,2,2 Gn32 Cr3,3,128 Gn32 Cr3,3,256 Gn32 Cr3,3,256 Gn32 Lbx32 Lby32 Cr1,1,32 Gn32 Lby32 Lbx32]
```

Pages are scaled to a height of 1,800 pixels, in colour.

**Classes:**
- **line types:** `default` and `stamp`;
- **regions:** `title`, `body`, `stamp_area`, `signature_area`, `footer`, `margin`, `identifier_area` and `table_cells`.

These are hocrsyngen's region names.

## Uses

- **Baseline segmentation of modern Hebrew document pages:** letters, notes, archive cards, ledgers, forms and notices, in print or handwriting-style fonts. It is best used with A1 for reading order and R3h for recognition.
- **A research baseline** for Hebrew document segmentation.

### Out of scope

- **Real scans,** without checking first. There is no reviewed real-page evaluation.
- **Layouts unlike hocrsyngen's seven templates.** This includes multi-column books, newspapers and manuscripts.
- **Reading order on its own.** kraken's heuristic order is poor with R4d (see below), so use A1.

## How to get started with the model

**The full pipeline (R4d + A1 + R3h).** This is the configuration the figures below come from. In a checkout of [heocr-engine](https://github.com/HeOCR/heocr-engine), run `pip install '.[kraken]'`, then:

```sh
heocr-engine kraken --api python \
  --segmentation-model heocr-r4d-segmentation.safetensors \
  --reading-order-model heocr-a1-reading-order.safetensors --reading-order-classes region \
  --recognition-model heocr-r3h-recognition.safetensors \
  page.jpg page.json
```

Tested end to end with kraken 7.0.2 on CPU, one seed-101 page in about 8 s. The text matched the scored prediction exactly.

**kraken alone** (no A1; kraken's heuristic line order):

```sh
kraken -i page.jpg page.txt segment -bl -d horizontal-rl -i heocr-r4d-segmentation.safetensors \
  ocr -m heocr-r3h-recognition.safetensors --reorder --base-dir R
```

- kraken 7.0.2 cannot use A1, for two reasons:
  - kraken gives it the segmenter's line types (`default`, `stamp`) rather than region types, and rejects the pair;
  - kraken's text output ignores a learned order ([mittagessen/kraken#820](https://github.com/mittagessen/kraken/issues/820)).
- kraken 7.0.2 sometimes aborts on exit ("recursive_mutex lock failed") after writing its output. Retrying works.

## Training details

### Training data

All synthetic. Nothing was scraped, and no real document or third-party text was used.

- **Pages:**
  - 1,800 pages from [hocrsyngen](https://github.com/HeOCR/hocrsyngen) at `8698895` (generator `s10c-gold-complete-v1`), seed 5101, over the seven templates. Region polygons come from the generator (S11a).
  - The split is 1,710 training pages (27,487 lines) and 90 validation pages (1,553 lines), assigned per page by hash.
- **Fonts:** Alef (1,286 pages) and Gveret Levin (514 pages), both SIL OFL 1.1. Credits are in NOTICE.
- **Text:**
  - The hocrsyngen corpus S10b (`hebrew_lines_train_v1.txt`, 439,596 bytes, sha256 `a3f2f0db…`).
  - It is original text authored by AI agents (Claude Opus 5.5 sessions) for HeOCR, with no third-party text, and dedicated to the public domain under CC0 1.0.

### Training procedure and hyperparameters

- **Initialisation:** from scratch. No `blla` or other third-party weights were loaded.
- **Trainer:** ketos 7.0.2 `segtrain` through `heocr-engine train-kraken-seg` (heocr-engine `aa67fa7`).
- **Optimiser:**
  - AdamW, learning rate 0.0002, constant schedule, weight decay 1e-5;
  - baseline width 8, baseline tolerance 10, dice weight 0.5, no augmentation.
- **Stopping:** early stopping with lag 8 (minimum 10 epochs). It stopped after 29 epochs; the best was epoch 20.
- **Validation:** mean IoU 0.8618. Baseline precision, recall and F1 at the best epoch were 0.9994, 0.9800 and 0.9890.
- **Run:** seed 42, on Apple `mps`. Not deterministic.

## Evaluation

### Testing data, factors and metrics

The batches are those of the R3h card. None was trained or tuned on, apart from the hocrgen fixture, a development set. All gold is synthetic.

#### Line geometry

Polygon IoU ≥ 0.5 against gold lines (heocr-engine `diagnose-segmentation`). `blla` is kraken's default segmenter, with `-d horizontal-rl`.

| Segmenter | Batch | P / R / F1 | F1, baseline match | Gold lines missed | Gold lines split | Kendall τ of line order |
|---|---|---|---|---|---|---|
| `blla` | seed-101 | 0.733 / 0.800 / 0.765 | 0.842 | 27 | 78 | 0.838 |
| R4d, kraken's heuristic order | seed-101 | 0.913 / 0.914 / 0.913 | 0.995 | 1 | 19 | 0.819 |
| R4d + A1 order | seed-101 | 0.913 / 0.914 / 0.913 | 0.995 | 1 | 19 | 1.000 |
| `blla` | held-out | 0.624 / 0.726 / 0.671 | 0.773 | 28 | 96 | 0.811 |
| R4d, kraken's heuristic order | held-out | 0.915 / 0.916 / 0.915 | 0.998 | 0 | 4 | 0.865 |
| R4d + A1 order | held-out | 0.915 / 0.916 / 0.915 | 0.998 | 0 | 4 | 1.000 |

**Stamps:** R4d matches 25 of 40 stamp lines on seed-101 and 35 of 40 on held-out.

#### End to end (R4d + A1 + R3h)

CER under hocrgen's `primary.v1` profile:

| Batch | R4d + A1 + R3h | `blla` + R3h |
|---|---|---|
| seed-101 | 0.020 | 0.168 |
| held-out | 0.010 | 0.238 |
| eval-mixed-heldout | 0.017 | 0.230 |
| eval-typo-heldout | 0.009 | 0.291 |
| eval-layout-heldout | 0.124 | 0.498 |
| hocrgen fixture (development set) | 0.130 | 0.404 |

## Bias, risks and limitations

- **The synthetic gap.** The evaluation pages share training's fonts, templates and degradations, so these scores overstate accuracy on real scans.
- **Split and merged lines:**
  - On seed-101, 19 gold lines are split, and 14 predicted lines each merge two gold lines.
  - Some stamp lines are merged into the body lines they overlap: 8 on seed-101.
- **Line order without A1 is poor.** kraken's heuristic reads separated stamp lines before the body lines around them (Kendall τ 0.819 on seed-101; 9 of 80 pages fully in order).
- **Ledgers:**
  - R4d's training pages predate hocrsyngen's S11b ledger layout, so newer ledger pages (the fixture, eval-layout-heldout) look unlike its training.
  - eval-layout-heldout's ledger CER is mostly hocrgen's ` | ` gold convention ([HeOCR/hocrgen#98](https://github.com/HeOCR/hocrgen/issues/98)).
- **kraken's polygonizer** sometimes reports "failed on line 0" on a page. The page still completes.
- **Layouts:** only hocrsyngen's seven templates were seen in training.

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
| Training batch | hocrsyngen `8698895`, seed 5101; manifest `29dffcca283770c56dedb4e53b57ccae289ec37124fd4399d968d93a3dd9295a`; line annotations `871355fdecb36fd561c1ee9832d8b6aec221685cca6ff3f13cad6b60cd6f36bf` |
| Training text | `a3f2f0db1bf48d8cdd618579af42ca36710cadf81cdc4d5e89d2dc6c192e6611` (hocrsyngen `hebrew_lines_train_v1.txt`) |
| Split | per page by hash, 5% validation; assignment `a794ebf3dbe5dd322cc85197a133207409fea0e487d02a23a52b0c76886d4006` |
| Training code | heocr-engine `aa67fa7`, ketos 7.0.2 |
| Training record | `r4d_training_run.json` (`heocr_engine_training_run.v1`), in this deposit |
| Scoring | hocrgen `2d3efb0` and `c8fb74e`; heocr-engine `55b0f7d` (end to end), `129c58e` and `eed1839` (line geometry) |

## Contact

Report problems and questions as issues on [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine/issues).

## Citation

Cite this model by its version DOI. <!-- DRAFT: the reserved version DOI (release/README.md, plan step 2). Never cite the concept DOI. -->
