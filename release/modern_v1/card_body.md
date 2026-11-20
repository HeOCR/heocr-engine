# HeOCR modern-v1: Hebrew office and modern-print recognition for Tesseract

modern-v1 is a [Tesseract](https://github.com/tesseract-ocr/tesseract) language model (`.traineddata`) for modern printed Hebrew: office documents, forms, tables, numbered sections and gazette print. HeOCR made it by fine-tuning Tesseract's own `heb` model from [tessdata_best](https://github.com/tesseract-ocr/tessdata_best) for one pass over 255,143 lines:
- 117,317 synthetic office-document lines and table cells, rendered by HeOCR in 12 open (SIL OFL 1.1) typefaces and degraded like office scans, photocopies and phone photos;
- 44,951 lines rendered from born-digital booklets of Israel's laws and regulations (Reshumot), labelled with the publisher's own text layer, and 34,217 more of those lines degraded the same way;
- 58,658 real scanned Reshumot lines, labelled with the same-wording text of the Open Law Book on Hebrew Wikisource.

No label is OCR output. It is the model that HeOCR's evaluation chose as the default for modern print in [heocr](https://github.com/HeOCR/heocr), the HeOCR document pipeline. (In the experiment records it is office-print v0, arm A, snapshot `snap_0160m_222700`.)

**Performance: not measured on a held-out set yet.** No held-out score yet; HeOCR will score it once in a registered held-out run. HeOCR reports accuracy only on held-out sets; the result will be added to this card in a new version.

- **How it was chosen:** first, its checkpoint: the lowest line CER on `office_val` (synthetic crops in a held-out face, from held-out booklets) among 11 candidates, the 9 snapshots, the training-best checkpoint and the final model. Then HeOCR's evaluation chose it as heocr's default for modern print in a pre-registered default-model study (2026-11-19). The study compared it with stock `heb` and the other arm, inside heocr, on HeOCR's open synthetic document sets, and on real-print development line sets. These sets made the choice, so no figure from them is reported here.
- **Known cost: some numbers stock read are now lost,** mostly outline labels such as `2.1.3`. heocr's own number handling is meant to catch these; it is not part of this model. Check numbers that matter.
- **For old print, use HeOCR [oldprint-v1](#related-models).**

| | |
|---|---|
| File | `heocr_modern_v1.traineddata` (trained as `heb.traineddata`; selected snapshot `snap_0160m_222700`), 3,704,077 bytes |
| sha256 | `6275943bf68f3d44ecc32f8d4c4195c890c96602111542ebe1f0ae0d8a6a5201` |
| Model type | recognition (line-level LSTM, CTC); Tesseract does the page layout |
| Format | Tesseract 4/5 LSTM `traineddata`, LSTM only (`--oem 1`; no legacy engine). Trained with Tesseract 5.5.3, built from its upstream tag |
| Base model | tessdata_best `heb.traineddata` at [`e12c65a`](https://github.com/tesseract-ocr/tessdata_best/tree/e12c65a915945e4c28e237a9b52bc4a8f39a0cec) (Apache-2.0), sha256 `dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5`, fine-tuned (modified) by HeOCR |
| Character set | the base model's, unchanged (no layer surgery) |
| Licence | Apache-2.0, Copyright (c) 2026 HeOCR maintainers (see LICENSE and NOTICE) |
| Training record | `modern_v1_training_run.json` (`heocr_tesseract_training_run.v1`) |
| Code | [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine); the experiment is [HeOCR/hocrsyngen `experiments/office_print_v0/`](https://github.com/HeOCR/hocrsyngen/tree/main/experiments/office_print_v0) |

## Uses

- **OCR of modern printed Hebrew documents:** office letters, forms, tenders, reports, tables and numbered sections, scanned, photocopied or photographed. Use it in place of Tesseract's `heb`.
- **The OCR step of a document pipeline.** heocr uses it for pages it reads by OCR.
- **Line recognition** of single printed Hebrew line images.

### Out of scope

- **Old and rabbinic print.** Use [oldprint-v1](#related-models).
- **Handwriting,** Rashi script and other non-square scripts. None was trained.
- **Niqqud (vowel points) and cantillation.** The labels have none, and pointed print comes out unpointed: it writes no points at all.
- **Text it cannot write.** Its character set is stock `heb`'s: it writes no maqaf `־`, geresh `׳`, gershayim `״`, en dash `–`, em dash `—` or `―`. Training labels with `–`, `—` or `―` were written `-`.
- **Unsupervised transcription.** Check the output, above all numbers.

## How to get started with the model

Install Tesseract 4 or 5 (trained with 5.5.3). Put `heocr_modern_v1.traineddata` in a directory, say `DIR`, and pass that directory and the language name `heocr_modern_v1`.

```sh
tesseract page.png out -l heocr_modern_v1 --tessdata-dir DIR --psm 3
```

For single line images, use `--psm 7`. In heocr, once the model is registered there:

```sh
heocr --download-model heocr_modern_v1
```

Notes:
- **`--tessdata-dir` replaces Tesseract's data directory.** Output formats other than plain text read their config files from `DIR/configs`. Link your installation's `configs` folder into `DIR`, or put the model in your installation's tessdata directory and drop `--tessdata-dir`.
- **The language name is the file name without `.traineddata`.** `-l heocr_modern_v1+eng` runs, but was not evaluated.

## Training details

### Training data

**Lines:** 255,143 in one seeded-shuffle list (seed 20261122), `lists_v2/arm_a.list` (sha256 `79c92cf2f92e763d1febd3a9e1778fe4a342053a25eab3f6a7e1acaaa67006c5`; labels sha256 `27dd590ea0d55f9ed7392f512cbd475b5442386e604332ae75db8427d674a298`).

| Part | Lines | Share | Rights |
|---|---|---|---|
| **O1:** synthetic office-document line and cell crops | 117,317 | 46.0% | CC0 (HeOCR); text PD-IL; fonts SIL OFL 1.1, not distributed |
| **Anchor:** Reshumot lines rendered from born-digital PDFs | 44,951 | 17.6% | PD-IL (Copyright Act 2007 §6) |
| **Degraded anchor:** the same kind of lines, degraded | 34,217 | 13.4% | PD-IL |
| **OLB:** scanned Reshumot lines, Open Law Book labels | 58,658 | 23.0% | scans PD-IL; labels CC BY-SA 4.0 (Hebrew Wikisource contributors) |

- **Text pool:** the born-digital Reshumot line text behind O1, the anchor and the degraded anchor comes from 107 booklets of *Sefer ha-Hukim* and *Kovetz ha-Takanot*. Before use, it lost every evaluation-reserved booklet, every exact hit on HeOCR's synthetic benchmark text and fixtures, and every line sharing a word 6-gram with a decontamination pool. Another 8 booklets (5%, chosen by a hash of the booklet id) were held out for checkpoint selection (`office_val`). No `office_val` booklet is in training.
- **O1:** 2,200 synthetic pages from HeOCR's `office_pages` generator ([HeOCR/hocrsyngen](https://github.com/HeOCR/hocrsyngen) `749069d`, seed 20261118), cut into 129,716 line and cell crops. The page families are numbered documents (654), tables (777), running text (554) and front matter (215).
  - **Degradation:** office scan (1,102 pages), photocopy (532), phone photo (328) and clean (238).
  - **Faces:** Arimo (383 pages), Cousine (367), Open Sans (340), Alef (137), Assistant (136), Frank Ruhl Libre (132), Rubik (132), Noto Sans Hebrew (125), Miriam Libre (124), Noto Serif Hebrew (113), David Libre (109) and Heebo (102). All are SIL OFL 1.1, from their upstream repositories or google/fonts `7af0d90`. **No proprietary or Microsoft face** (Arial, Times New Roman, David, Narkisim, Miriam, Arial Unicode MS or any other) was used, and none of HeOCR's benchmark documents made with such faces was trained on. One more face, Tinos, was used only for `office_val`.
  - **Gates:** a crop was rejected if it lost its ink, went flat, stopped resembling its clean render, or stock Tesseract failed on it while reading its clean render well. 123,486 crops passed.
- **Degraded anchor:** 41,000 anchor lines, each skewed up to ±1° and degraded by one of O1's photometric models. 35,848 passed the same gates.
- **OLB:** a seeded sample (seed 20261121) of the 136,903 training lines of `olbreshumotlines_v1`. These are scans of Reshumot booklets, labelled with the same-wording text of ספר החוקים הפתוח (the Open Law Book) on Hebrew Wikisource. The training record lists each Wikisource page by revision id and permalink. Under heocr-engine decision 0016, the weights stay Apache-2.0 with the Wikisource credit, and no word list was built from that text.
- **Decontamination:** HeOCR's evaluation ran its official overlap check (`check_train_overlap`: word 6-grams after folding, against every evaluation target, restricted ones included) on the whole list. It first found 5,507 hitting lines, and they were dropped: O1 2,683, anchor 730, degraded anchor 559 and OLB 1,535. The rebuilt list is **CLEAN, with 0 hits on every target** (2026-11-18).
- **Labels stock's character set cannot encode:** 1,352 lines (0.53%), with Latin letters, `□` or `”`. lstmtraining skips them.

### Training procedure

- **Start:** stock tessdata_best `heb` (`--continue_from` its LSTM, `--old_traineddata` itself). The network is unchanged.
- **Trainer:** `lstmtraining`, Tesseract 5.5.3 built from its upstream tag (commit `db0ec62f…`), on a 32-vCPU CPU pod, `--learning_rate 0.0001`, one epoch (255,143 iterations), with a snapshot every 20 minutes. The run exited cleanly; the pod checked every input's sha256 before training.
- **Truth order:** labels in Tesseract's LSTM training order, converted with `tesseract … --psm 13 lstm.train`.
- **Selection:** the lowest line CER on `office_val` under the `line_fold_v1` profile (below), over 9 snapshots, the training-best checkpoint and the final model. `office_val` is 4,851 synthetic crops in the held-out face Tinos, from held-out booklets, decontaminated like the training list. The winner is `snap_0160m_222700` (iteration 222,700). **`office_val` is drawn from the training distribution, so it picks a snapshot and says nothing about performance.**
- **Arms:** an equal-compute arm on the real lines only (anchor and OLB) was compared on development sets and not chosen. It is not released.
- **One training run.** It is not deterministic, and the bytes are not reproducible.

### Word list

The word list is tessdata_best's own, unchanged: the model's `lstm-word-dawg` has the base model's sha256, `f34e9fa5165077f285ccff7c0f53a8e96b74ef37c92038e472770cfc83433171`. No entry comes from any training text.

## Evaluation

**Not measured on a held-out set yet.** HeOCR reports a model's accuracy only on sets held out from its training, selection and tuning. modern-v1 has no such score yet:

- **What was used to choose it is not reported as performance.** The development, tuning and selection sets behind the choice (`office_val`, HeOCR's open synthetic document sets, and the real-print development line sets) are named in the experiment records: hocrsyngen `experiments/office_print_v0/RESULTS.md` and evaluation's default-model study report.
- **Next:** HeOCR's registered held-out run of the default model, against stock tessdata_best `heb` (the base), shown beside it and read the same way. Its result will be added in a new version of this card.
- **Scoring profile** for that run: `line_fold_v1` (sha256 `2e2627104be4f27dc3204787dd3ff4f8591d95d1d96294c65833d2773041d317`): NFC, whitespace collapsed, and the folds `־`→`-`, `׳`→`'`, `״`→`"`, `“ ” „`→`"`, `—`→`–`. A reference `–` or `―` costs every stock-charset model one substitution.

## Bias, risks and limitations

- **Not measured on a held-out set yet.** See [Evaluation](#evaluation).
- **Lost numbers.** On synthetic development scans it loses some numbers that stock reads, mostly outline labels. Check numbers that matter.
- **Synthetic share.** 46% of its lines are synthetic office pages in 12 open faces. Real office documents set in proprietary faces (Arial, David, Times New Roman and others) were never trained on; it was developed only against open look-alike faces (Arimo, Cousine, Tinos).
- **One source of real text.** All its real and rendered lines are Reshumot laws and regulations. Other registers may gain less.
- **Gate bias.** The training gates keep what stays legible, so the heaviest photocopy damage drawn is under-represented (about 20% photocopy against 25% planned).
- **Pointed text comes out unpointed.** HeOCR's held-out pointed-print run found that it writes no niqqud. Read its output as unpointed text.
- **Character set.** It cannot write `־ ׳ ״ – — ―`, or Latin letters.
- **Layout is Tesseract's,** or heocr's when used inside heocr. The model changes only the line recognizer.
- **One training run.** Training-seed variation is not measured.

## Related models

- **HeOCR oldprint-v1** (`heocr_oldprint_v1`): the same release round, for old and rabbinic print. heocr routes old print to it.
- **HeOCR R8b** and **R7**: earlier HeOCR models for printed Hebrew, continued from R7; modern-v1 is not derived from them.

## Licence and attribution

- **Licence:** Apache-2.0. Copyright (c) 2026 HeOCR maintainers.
- **Base model:** a modified (fine-tuned) version of tessdata_best `heb`, Apache-2.0, from the Tesseract OCR project.
- **NOTICE:** redistributions must keep the NOTICE file. It credits:
  - the tessdata_best base model and Tesseract;
  - Reshumot, the official gazette of the State of Israel, for the laws and regulations;
  - Hebrew Wikisource contributors for the Open Law Book text (CC BY-SA 4.0);
  - the authors of the 12 typefaces behind the synthetic lines (SIL OFL 1.1).
- **No endorsement.** Neither Reshumot or the State of Israel, Wikisource, the Tesseract project nor the typeface authors endorses HeOCR or this model.
- **The model contains no images, fonts or text files.**

## Provenance and reproduction

| Part | Identity |
|---|---|
| Base model | tessdata_best `heb.traineddata` at `e12c65a915945e4c28e237a9b52bc4a8f39a0cec`, sha256 `dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5` |
| Training list | `lists_v2/arm_a.list`, sha256 `79c92cf2…`; labels `27dd590e…`; inputs manifest `8f2bbd9a3e42061629c7e83f96517f3d64cf9d684a4d00c6e86deed58c6ec258` |
| Synthetic generator | HeOCR/hocrsyngen `749069d`, `office_pages`, seed 20261118 |
| Training | Tesseract 5.5.3 `lstmtraining`, 2026-11-18, run `20261118-171942-dd68`; selected snapshot `snap_0160m_222700` |
| Selection | `office_val_sel`, 4,851 crops, sha256 `d77a7fa79c398208bfabe51db4cd982190bcdd9233eed5bbad1d1cec8ea88e51` |
| Records | hocrsyngen `experiments/office_print_v0/` (REGISTRATION.md with amendments 1 and 2, RESULTS.md); evaluation's default-model study report |
| Training record | `modern_v1_training_run.json`, in this deposit |

## Contact

Report problems and questions as issues on [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine/issues). A rights concern can be raised the same way, or by email to heocrproject@gmail.com. The takedown procedure is at [heocr.github.io/rights.html](https://heocr.github.io/rights.html).

## Citation

Cite this model by its version DOI: [10.5281/zenodo.24372349](https://doi.org/10.5281/zenodo.24372349).
