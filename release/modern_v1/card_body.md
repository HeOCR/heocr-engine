# HeOCR modern-v1: Hebrew office and modern-print recognition for Tesseract

modern-v1 is a [Tesseract](https://github.com/tesseract-ocr/tesseract) language model (`.traineddata`) for modern printed Hebrew: office documents, forms, tables, numbered sections and gazette print. HeOCR made it by fine-tuning Tesseract's own `heb` model from [tessdata_best](https://github.com/tesseract-ocr/tessdata_best) for one pass over 255,143 lines:
- 117,317 synthetic office-document lines and table cells, rendered by HeOCR in 12 open (SIL OFL 1.1) typefaces and degraded like office scans, photocopies and phone photos;
- 44,951 lines rendered from born-digital booklets of Israel's laws and regulations (Reshumot), labelled with the publisher's own text layer, and 34,217 more of those lines degraded the same way;
- 58,658 real scanned Reshumot lines, labelled with the same-wording text of the Open Law Book on Hebrew Wikisource.

No label is OCR output. It is the model that HeOCR's evaluation chose as the default for modern print in [heocr](https://github.com/HeOCR/heocr), the HeOCR document pipeline. (In the experiment records it is office-print v0, arm A, snapshot `snap_0160m_222700`.)

**What it gains, and what it costs.** Every figure on this card is from development or tuning sets: **there is no test score.**
- **Inside heocr, on HeOCR's open synthetic document sets,** it lowers page CER against heocr with stock `heb` inside on every OCR cell: scanned PDFs under a wrong text layer (T4) from 2.87% to 1.04%, image-only PDFs (T5) from 4.22% to 2.75%, and scanned tables from 1.58% to 0.42%. Missed numbers fall from 20.0% to 4.6% (T4) and from 13.2% to 4.0% (T5). Text-layer documents are unchanged.
- **On 12 real-print line sets,** it is better than stock `heb` on every one, by 3.5 to 7.4 CER points.
- **The cost: some numbers it used to read are now lost.** On 42 open synthetic office scans it gains 268 numbers and loses 83 against stock. 49 of the 83 losses are outline labels such as `2.1.3`. heocr's own number handling is meant to catch these; it is not part of this model.
- **On old print, HeOCR [oldprint-v1](#related-models) reads better.** On all 7 old-print line sets measured, oldprint-v1 has the lower CER, by 0.1 to 3.0 points.

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
- **The OCR step of a document pipeline.** heocr uses it for pages it reads by OCR. Its figures above come from that use.
- **Line recognition** of single printed Hebrew line images.

### Out of scope

- **Old and rabbinic print.** Use [oldprint-v1](#related-models).
- **Handwriting,** Rashi script and other non-square scripts. None was trained.
- **Niqqud (vowel points) and cantillation.** The labels have none.
- **Text it cannot write.** Its character set is stock `heb`'s: it writes no maqaf `־`, geresh `׳`, gershayim `״`, en dash `–`, em dash `—` or `―`. Training labels with `–`, `—` or `―` were written `-`.
- **Unsupervised transcription.** Check the output, above all numbers.

## How to get started with the model

Install Tesseract 4 or 5 (trained with 5.5.3). Put `heocr_modern_v1.traineddata` in a directory, say `DIR`, and pass that directory and the language name `heocr_modern_v1`.

```sh
tesseract page.png out -l heocr_modern_v1 --tessdata-dir DIR --psm 3
```

For single line images, use `--psm 7`; the line-set figures below were read that way. In heocr, once the model is registered there:

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
- **Selection:** the lowest line CER on `office_val` under the `line_fold_v1` profile (below), over 9 snapshots, the training-best checkpoint and the final model. `office_val` is 4,851 synthetic crops in the held-out face Tinos, from held-out booklets, decontaminated like the training list. The winner is `snap_0160m_222700` (iteration 222,700) at 1.375% CER; stock `heb` is 14.754% there. **`office_val` is drawn from the training distribution, so it picks a snapshot and says nothing more.**
- **Arms:** an equal-compute arm on the real lines only (anchor and OLB) was worse wherever a difference was resolved. It is not released.
- **One training run.** It is not deterministic, and the bytes are not reproducible.

### Word list

The word list is tessdata_best's own, unchanged: the model's `lstm-word-dawg` has the base model's sha256, `f34e9fa5165077f285ccff7c0f53a8e96b74ef37c92038e472770cfc83433171`. No entry comes from any training text.

## Evaluation

- **No test score.** Every figure is from a development or tuning set. HeOCR's registered held-out run of the default model comes later.
- **Source:** HeOCR evaluation's default-model study (2026-11-19, pre-registered before any output was read) and the office-print v0 results. All figures are aggregates.
- **Metric:** CER (%), and number misses (%) where shown.
- **Scoring profile `line_fold_v1`** (sha256 `2e2627104be4f27dc3204787dd3ff4f8591d95d1d96294c65833d2773041d317`): NFC, whitespace collapsed, and the folds `־`→`-`, `׳`→`'`, `״`→`"`, `“ ” „`→`"`, `—`→`–`. A reference `–` or `―` costs every stock-charset model one substitution.
- **Stock Tesseract** (tessdata_best `heb` at `e12c65a`, the base) is shown beside every figure, read the same way.

### HeOCR's open synthetic document sets, inside heocr (tuning)

Page CER %, with missed numbers % in brackets, heocr at `1b53753`. These are HeOCR's open synthetic tuning sets, which heocr itself is developed against: not held out.

| Cell | heocr with stock `heb` | **heocr with modern-v1** | upper bound of the difference |
|---|---|---|---|
| Scanned PDF under a wrong text layer (T4) | 2.87 (20.0) | **1.04 (4.6)** | CER −1.53, misses −13.2 |
| Image-only PDF (T5) | 4.22 (13.2) | **2.75 (4.0)** | CER −1.25, misses −7.5 |
| Scanned tables | 1.58 (2.59) | **0.42 (0.55)** | CER −0.95 |
| Correct OCR layer kept (T6) | 0.12 (0.22) | **0.05 (0.06)** | |

- **Text-layer documents** (DOCX, DOC, PDF text layers) are identical with either model.
- **Upper bound:** of the 95% paired bootstrap interval over documents, for modern-v1 minus stock. Below 0 means better.
- **Grainy JPEG tables (stress set):** CER 12.24% with stock inside, 9.82% with modern-v1.

### Numbers gained and lost

On 42 open synthetic office scans, document by document against stock:

| | gained | lost | lost: outline labels | lost: other |
|---|---|---|---|---|
| modern-v1 | **268** | **83** | 49 | 34 |

Every one of the 42 documents changes. Most losses are outline labels (`2.1.3`-style section numbers).

### Real print, line sets (dev)

Every line of each list read at psm 7 and scored under `line_fold_v1`. Δ is modern-v1 − stock, with its 95% paired bootstrap interval over lines (10,000 resamples, seed 0).

| List | Lines | stock `heb` | **modern-v1** | Δ [95%] |
|---|---|---|---|---|
| Scanned Reshumot, OLB dev | 3,254 | 5.428 | **1.902** | −3.527 [−3.637, −3.421] |
| Scanned Reshumot, OLB dev v1.1 | 3,325 | 5.410 | **1.905** | −3.505 [−3.612, −3.397] |
| Reshumot rendered dev | 2,716 | 6.613 | **0.866** | −5.747 [−6.252, −5.304] |
| *Kevar* (1922), held out | 4,600 | 5.677 | **1.054** | −4.623 [−4.733, −4.520] |
| *Yedi'ot ha-Teva* (1883), held out | 4,600 | 9.218 | **3.849** | −5.369 [−5.495, −5.248] |
| Brainin, IA scan | 6,257 | 5.071 | **1.514** | −3.557 [−3.624, −3.489] |
| Brainin, NLI scan | 4,046 | 10.450 | **4.224** | −6.226 [−6.384, −6.070] |
| Silman, *Sansinim* | 3,046 | 5.824 | **1.728** | −4.096 [−4.214, −3.983] |
| Mekhilta (rabbinic) | 3,141 | 7.512 | **2.895** | −4.617 [−4.715, −4.520] |
| Wikisource dev | 257 | 14.672 | **8.812** | −5.860 [−6.300, −5.439] |
| Bodek | 21 | 15.684 | **8.311** | −7.373 [−10.077, −4.750] |
| R8b selection lines | 3,000 | 7.549 | **2.520** | −5.029 [−5.181, −4.885] |

- **Better than stock on every list**, with every interval below 0.
- **On these lines it is not HeOCR's strongest model.** oldprint-v1 is better on 3 of the 5 modern lists, and on all 7 old-print lists by 0.1 to 3.0 points. modern-v1's lead is on whole documents inside heocr (page segmentation, office faces, tables), where it was chosen.

### Development documents (reference-free)

On HeOCR's 30 development PDFs, the dictionary-hit rate is 80.20% with stock inside and 80.23% with modern-v1 (+0.03 [+0.00, +0.08]). No reference-free veto fires (reversed amounts, replacement characters). These PDFs are almost all text-layer pages, so the model touches few of them.

## Bias, risks and limitations

- **No test score.** The tuning sets are synthetic and open, and heocr is developed against them. The line sets are dev.
- **Lost numbers.** It loses 83 numbers that stock reads on 42 synthetic office scans, mostly outline labels. Check numbers that matter.
- **Synthetic share.** 46% of its lines are synthetic office pages in 12 open faces. Real office documents set in proprietary faces (Arial, David, Times New Roman and others) were never trained on; how it reads them is measured only through open look-alike faces (Arimo, Cousine, Tinos).
- **One source of real text.** All its real and rendered lines are Reshumot laws and regulations. Other registers may gain less.
- **Gate bias.** The training gates keep what stays legible, so the heaviest photocopy damage drawn is under-represented (about 20% photocopy against 25% planned).
- **Character set.** It cannot write `־ ׳ ״ – — ―`, or Latin letters.
- **Layout is Tesseract's,** or heocr's when used inside heocr. The model changes only the line recognizer.
- **One training run.** The intervals cover sampling, not training seeds.

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

Cite this model by its version DOI: DOI-TO-BE-RESERVED.
