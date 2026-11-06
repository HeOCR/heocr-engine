# HeOCR A1: Hebrew document line reading order (kraken)

A1 is a [kraken](https://kraken.re) reading-order model. It orders the text lines of a modern Hebrew document page from each line's position and its region type: title, body, stamp, signature, footer, margin, identifier or table cell. HeOCR trained it from scratch on synthetic pages only.

A1 is the reading-order step of HeOCR's three-model pipeline:
- **R4d** finds the lines and their regions;
- **A1** puts them in reading order;
- **R3h** reads them.

The three are released together, as separate records that link to each other (see [The pipeline](#the-pipeline)).

It is a research baseline. All of its evaluation is on synthetic pages; no reviewed evaluation on real scans exists yet.

| | |
|---|---|
| File | `heocr-a1-reading-order.safetensors` (trained as `best_0.0000.safetensors`), 8,492 bytes |
| sha256 | `69aa1946583bb68ddf13ef20860582f4aa982a46b2f79e38bd7d9ae20535fb56` |
| Model type | reading order (line level, `--level baselines`) |
| Format | kraken safetensors; trained with ketos 7.0.2 `rotrain` |
| Licence | Apache-2.0, Copyright (c) 2026 HeOCR maintainers (see LICENSE and NOTICE) |
| Training record | `a1_training_run.json` (`heocr_engine_training_run.v1`, reconstructed from the run's evidence) |
| Code | [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine) |

## The pipeline

| Step | Model | Record |
|---|---|---|
| Segmentation: baselines, line polygons, typed regions | R4d, `heocr-r4d-segmentation.safetensors` (`d32cd1a8…`) | <!-- DRAFT: R4d's reserved version DOI (release/README.md, plan step 2) --> |
| Reading order: line order from each line's region type | A1, this model | <!-- DRAFT: A1's reserved version DOI (release/README.md, plan step 2) --> |
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

- **Network:** kraken's line reading-order network (`ROMLP`), a two-layer perceptron with about 1.9 K parameters. It compares pairs of lines.
- **Inputs:** for each line, its baseline's start, end and centre, and a one-hot class.
- **Classes:** the line's region type: `default` 0, `title` 1, `body` 2, `stamp_area` 3, `signature_area` 4, `footer` 5, `margin` 6, `identifier_area` 7, `table_cells` 8.

**Why region types.** The same network trained with R4d's line types (`default`, `stamp`) could not order archive cards or ledgers. Nothing told a label from a body line at the same height. With region types it can.

**How heocr-engine tags R4d's lines** (`--reading-order-classes region`):
1. `stamp_area` if R4d typed the line `stamp`;
2. otherwise the first region kraken lists for the line;
3. otherwise `default`.

On matched lines, the predicted type equalled the gold region for every line in all four batches checked.

## Uses

- **Reading order for R4d's lines** on modern Hebrew document pages, inside the R4d + A1 + R3h pipeline.
- **A research baseline** for learned reading order on Hebrew documents.

### Out of scope

- **Segmenters other than R4d.** A1 depends on R4d's region types and `stamp` line type.
- **kraken's own pipeline** in version 7.0.2 (see below).
- **Real scans,** and layouts unlike hocrsyngen's templates.

## How to get started with the model

Use A1 through heocr-engine's in-process kraken stage. In a checkout of [heocr-engine](https://github.com/HeOCR/heocr-engine), run `pip install '.[kraken]'`, then:

```sh
heocr-engine kraken --api python \
  --segmentation-model heocr-r4d-segmentation.safetensors \
  --reading-order-model heocr-a1-reading-order.safetensors --reading-order-classes region \
  --recognition-model heocr-r3h-recognition.safetensors \
  page.jpg page.json
```

- **Tested** end to end with kraken 7.0.2 on CPU, on one seed-101 page in about 8 s. The text matched the scored prediction exactly, and 8 of the page's 10 lines were moved by the learned order.
- **`--geometry-output geometry.json`** also writes the ordered line geometry and the predicted regions.

**kraken 7.0.2 alone cannot use A1:**
- A1's classes are region types, but kraken's neural reading order encodes the segmenter's line types. `ketos convert` can combine R4d and A1 into one file, but `kraken segment` then stops with "Reading order model class mapping … does not match segmentation model".
- kraken's text output ignores a learned line order in any case ([mittagessen/kraken#820](https://github.com/mittagessen/kraken/issues/820)).

## Training details

### Training data

All synthetic. Nothing was scraped, and no real document or third-party text was used.

- **Pages:** 3,990 training and 210 validation pages from two hocrsyngen batches, re-prepared so that each line's class is its region type.
  - **R4d's training batch:** hocrsyngen `8698895`, seed 5101; 1,710 / 90 pages.
  - **R3d's training batch:** hocrsyngen `db3f73c` (generator `s11b-ledger-fit-v1`), seed 7101; 2,280 / 120 pages.
  - The pages cover the seven templates, 565–573 per template in training.
  - That gives 2,181,264 training line pairs.
- **Fonts:** Alef (3,000 pages) and Gveret Levin (1,200 pages), both SIL OFL 1.1. Credits are in NOTICE.
- **Text:**
  - The batches were rendered from the hocrsyngen corpora S10b (R4d's batch) and S10b + S13a (R3d's batch).
  - The text is original, authored by AI agents (Claude Opus 5.5 sessions) for HeOCR, with no third-party text, and dedicated to the public domain under CC0 1.0.
  - A1 sees line positions and classes, not the text itself.

### Training procedure and hyperparameters

- **Initialisation:** from scratch.
- **Trainer:** ketos 7.0.2 `rotrain -f page --level baselines`. The classes were passed by `--config`, because of [mittagessen/kraken#821](https://github.com/mittagessen/kraken/issues/821).
- **Stopping:** early stopping with lag 10 and a minimum of 30 epochs. It ran 30 epochs.
- **Validation:** `val_spearman` (kraken's normalised Spearman footrule distance; 0 is a perfect order) reached 0.0 from epoch 26 on the 210 validation pages.
- **Run:** seed 42, on Apple `mps`. Not deterministic.
- **Training record:** heocr-engine has no reading-order training command, so the record was written afterwards from the run's command, config, ketos log and data summaries. It lists what that evidence cannot supply:
  - the ketos defaults that were not logged;
  - the precision and determinism settings;
  - why training stopped at 30 epochs;
  - which of epochs 26–29 the kept file comes from.

## Evaluation

### Testing data, factors and metrics

The batches are those of the R3h card. None was trained or tuned on, except the hocrgen fixture: A1's design (region-type classes, stamp-first tagging) was chosen on it, so it is a development set. All gold is synthetic.

#### Order alone

Pages fully in order over matched lines, with R4d's lines. Kendall τ is shown where pages are out of order.

| Batch | kraken's heuristic | A1 |
|---|---|---|
| seed-101 | 9 / 80 (τ 0.819) | 80 / 80 |
| held-out | 12 / 80 (τ 0.865) | 80 / 80 |
| eval-mixed-heldout | 11 / 80 (τ 0.853) | 80 / 80 |
| fixture `archive_card` (development set) | 3 / 25 (τ 0.917) | 15 / 25 (τ 0.992) |
| fixture `ledger` (development set) | 0 / 25 (τ 0.774) | 25 / 25 |

On eval-layout-heldout, a fresh batch of cards and ledgers made after A1 was fixed, A1's text equals the gold-order text on every card and ledger page.

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

- **Long archive cards:**
  - On the fixture, 10 of 25 cards are still out of order. Each has one discordant pair: the sixth and lowest body line is read after the first label.
  - Six-body-line cards are rare in training: 18 of 1,199 cards.
- **It depends on R4d's region types.** A wrong region tag gives a wrong class. Tagging was exact on the batches checked, but those are synthetic.
- **The synthetic gap.** Only hocrsyngen's templates were seen in training, so real documents can have orders it never learned.
- **It needs heocr-engine** with kraken 7.0.2 (see above).

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
| Training batches | hocrsyngen `8698895`, seed 5101 (manifest `29dffcca283770c56dedb4e53b57ccae289ec37124fd4399d968d93a3dd9295a`, annotations `871355fdecb36fd561c1ee9832d8b6aec221685cca6ff3f13cad6b60cd6f36bf`); hocrsyngen `db3f73c`, seed 7101 (manifest `e8098844b7dfb7027913d7a04e4a5d35100ab551d41bb759ec92f0f685c2ec73`, annotations `51cab2f331607035f8a697ca3ffdcbff40241a65821fb4634dd80412b4e59c43`) |
| Training text | `a3f2f0db1bf48d8cdd618579af42ca36710cadf81cdc4d5e89d2dc6c192e6611` (S10b) and `e4384322e167f81252f28703206f180d1757e789c3ef7bd97484eef6978b1cf4` (S10b + S13a) |
| Data preparation | heocr-engine `5294ca5` `prepare-kraken-data --task segmentation`, each region name as its own line type |
| Training | ketos 7.0.2 `rotrain`, 2026-11-04 |
| Training record | `a1_training_run.json` (`heocr_engine_training_run.v1`), in this deposit |
| Scoring | hocrgen `2d3efb0` and `c8fb74e`; heocr-engine `4e09858` and `660e5a4` (order), `55b0f7d` (end to end with R3h) |

## Contact

Report problems and questions as issues on [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine/issues).

## Citation

Cite this model by its version DOI. <!-- DRAFT: the reserved version DOI (release/README.md, plan step 2). Never cite the concept DOI. -->
