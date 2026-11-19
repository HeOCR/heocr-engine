# HeOCR oldprint-v1: Hebrew old and rabbinic print recognition for Tesseract

oldprint-v1 is a [Tesseract](https://github.com/tesseract-ocr/tesseract) language model (`.traineddata`) for old printed Hebrew in the square script: 19th- and early-20th-century books and rabbinic editions. HeOCR made it by continuing to train [HeOCR R7](https://doi.org/10.5281/zenodo.24126449), itself a fine-tune of Tesseract's own `heb` model from [tessdata_best](https://github.com/tesseract-ocr/tessdata_best), for one pass over 76,946 lines:
- 22,910 real scanned lines from 4 public-domain books (Internet Archive scans), labelled with the Project Ben-Yehuda transcription of the same edition;
- 14,036 real scanned lines from 3 rabbinic editions (Internet Archive scans), labelled with public-domain Sefaria texts and Project Gutenberg ebook #43740;
- 40,000 lines rendered from born-digital booklets of Israel's laws and regulations (Reshumot), labelled with the publisher's own text layer, replayed so that modern print is not lost.

No label is OCR output. It is the model that HeOCR's evaluation recommends for old print in [heocr](https://github.com/HeOCR/heocr), the HeOCR document pipeline, beside [modern-v1](#related-models) for modern print. (In the experiment records it is P-hist round v1, arm r7, `heb_final`.)

**What it gains, and what it costs.** Every figure on this card is from development sets: **there is no test score.** HeOCR's P-hist test set has no references yet.
- **On 38 old-print pages from 13 books (audit2),** whole pages read at psm 3, it lowers CER from stock `heb`'s 20.26% to 16.75%, and from R7's 18.33%. audit2 chose this model among 20 candidates, so the figure is optimistic. Against stock, the 95% interval over books, −3.51 [−6.10, +0.30], still includes 0.
- **On 12 real-print line sets,** it is better than stock on every one, by 3.2 to 10.7 CER points. It is better than R7 on 9 of the 12, and repairs R7's loss on modern Reshumot print.
- **The cost: it is not for modern office documents.** Inside heocr, on HeOCR's open synthetic office sets, it reads worse than stock `heb` on scanned PDFs under a wrong text layer (T4, 3.92% CER against 2.87%), image-only PDFs (T5, 5.13% against 4.22%) and scanned tables (2.89% against 1.58%). Use modern-v1 there.

| | |
|---|---|
| File | `heocr_oldprint_v1.traineddata` (trained as `heb.traineddata`; selected checkpoint `heb_final`), 3,628,595 bytes |
| sha256 | `f8090760b5b02d09cf4ddb435e7a5e34089f6f17cde9cfb6c67fd06c6f17ec02` |
| Model type | recognition (line-level LSTM, CTC); Tesseract does the page layout |
| Format | Tesseract 4/5 LSTM `traineddata`, LSTM only (`--oem 1`; no legacy engine). Trained with Tesseract 5.5.3, built from its upstream tag |
| Continued from | HeOCR R7 ([10.5281/zenodo.24126449](https://doi.org/10.5281/zenodo.24126449)), `heocr_r7.traineddata`, sha256 `95faab81fba6fe57f854f973c1ccad2b0d1059fb951f34b17277385ceea8b303` |
| Base model | tessdata_best `heb.traineddata` at [`e12c65a`](https://github.com/tesseract-ocr/tessdata_best/tree/e12c65a915945e4c28e237a9b52bc4a8f39a0cec) (Apache-2.0), sha256 `dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5`, fine-tuned (modified) by HeOCR as R7 and then oldprint-v1 |
| Character set | R7's, unchanged: stock `heb`'s plus the maqaf `־` and the en dash `–` |
| Licence | Apache-2.0, Copyright (c) 2026 HeOCR maintainers (see LICENSE, NOTICE and NOTICE.r7) |
| Training record | `oldprint_v1_training_run.json` (`heocr_tesseract_training_run.v1`) |
| Code | [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine); the experiment is [HeOCR/hocrsyngen `experiments/phist_v1/`](https://github.com/HeOCR/hocrsyngen/tree/main/experiments/phist_v1) |

## Uses

- **OCR of old printed Hebrew** in the square script without niqqud: 19th- and early-20th-century books, and rabbinic editions set in square type. Use it in place of Tesseract's `heb` or R7.
- **The old-print step of a document pipeline.** heocr routes old print to it.
- **Line recognition** of single printed Hebrew line images, and **a research baseline** for old Hebrew print.

### Out of scope

- **Modern office documents, forms and tables.** Use [modern-v1](#related-models).
- **Rashi script** and other non-square scripts. Every training line is square type.
- **Handwriting.**
- **Niqqud (vowel points) and cantillation.** The labels have none.
- **Text it cannot write:** geresh `׳`, gershayim `״`, the em dash `—` and Latin letters. Training labels wrote `׳ ״` as `' "` and `—` as `–`.
- **Unsupervised transcription.** Check the output.

## How to get started with the model

Install Tesseract 4 or 5 (trained with 5.5.3). Put `heocr_oldprint_v1.traineddata` in a directory, say `DIR`, and pass that directory and the language name `heocr_oldprint_v1`.

```sh
tesseract page.png out -l heocr_oldprint_v1 --tessdata-dir DIR --psm 3
```

The audit2 figures were read this way, whole pages at psm 3. The line-set figures were read at psm 7. In heocr, once the model is registered there:

```sh
heocr --download-model heocr_oldprint_v1
```

Notes:
- **`--tessdata-dir` replaces Tesseract's data directory.** Output formats other than plain text read their config files from `DIR/configs`. Link your installation's `configs` folder into `DIR`, or put the model in your installation's tessdata directory and drop `--tessdata-dir`.
- **Maqaf and dashes.** It writes the maqaf `־` (U+05BE) where many texts write `-`. Fold it if your downstream text uses the ASCII form.

## Training details

### Training data

**Lines:** 76,946 in one seeded-shuffle list (seed 20261130), `phist_r7.list` (sha256 `0cd3e7e8788f3c278ae9083f953a88f7319c70910d75423d0349733f7f72820c`; labels sha256 `bbdaade092892644bea4397061cbc1a88f9537a5f59412e12c0b0ab59c9cf33b`).

| Source | Line set | Lines | Share | Rights |
|---|---|---|---|---|
| 4 Internet Archive book scans, Ben-Yehuda labels | `bynli_lines_v3` | 22,910 | 29.8% | Internet Archive, original conditions apply; text public domain |
| 3 Internet Archive scans of rabbinic editions, Sefaria and Project Gutenberg labels | `rablines_v1` | 14,036 | 18.2% | Internet Archive, original conditions apply; texts public domain |
| Reshumot lines rendered from born-digital PDFs (replay) | office-print v0 anchor, decontaminated | 40,000 | 52.0% | PD-IL (Copyright Act 2007 §6) |

- **The books and editions,** each capped at 8% of the round:

  | Source | Record | Book | Lines |
  |---|---|---|---|
  | IA | [zikhronotlebetda01reck](https://archive.org/details/zikhronotlebetda01reck) | Abraham Shalom Friedberg (d. 1902), *Zikhronot le-Vet David*, Warsaw, 1893 | 6,099 |
  | IA (Google-derived) | [mahzor-vitri-abraham-berliner-1893](https://archive.org/details/mahzor-vitri-abraham-berliner-1893) | Simhah ben Samuel of Vitry, *Machzor Vitry*, ed. Simeon Hurwitz, Berlin: Mekize Nirdamim, 1889–97 | 6,077 |
  | IA | [midrashleaovhame0305tobi](https://archive.org/details/midrashleaovhame0305tobi) | Tobiah ben Eliezer, *Midrash Lekach Tov*, ed. Salomon Buber (d. 1906), Vilna, 1884, vols 3–5 | 6,063 |
  | IA (Google) | [afahleneemaniml00fngoog](https://archive.org/details/afahleneemaniml00fngoog) | Samuel Joseph Fuenn (d. 1891), *Safah le-Ne'emanim*, Vilna, 1881 | 5,749 |
  | IA | [kolkitveylkatsen018800](https://archive.org/details/kolkitveylkatsen018800) | Judah Leib Katzenelson (d. 1917), *Kol Kitve Y. L. Katsenelson*, St Petersburg, 1905 | 5,712 |
  | IA | [seferhademaotmeo0000bern](https://archive.org/details/seferhademaotmeo0000bern) | Simon Bernfeld (d. 1940), *Sefer ha-Dema'ot*, Berlin, 1923 | 5,350 |
  | IA | [betnekhothahalak01horouoft](https://archive.org/details/betnekhothahalak01horouoft) | *Bet Nekhot ha-Halakhot o Toratan shel Rishonim*, part I, ed. Chaim Meir Horowitz, Frankfurt am Main, 1881 | 1,896 |

- **Book audit:** only books whose labels passed a per-book audit were used: at most 1 word error in 32 seeded lines. Books that failed it were left out.
- **Internet Archive scans:** five were scanned by university libraries (Robarts – University of Toronto; University of Illinois Urbana-Champaign; University of Toronto, Downsview), named in the NOTICE. Two are Google-class scans, retrieved via the Internet Archive, not from Google or NLI:
  - `afahleneemaniml00fngoog`, digitized by Google (contributing library: University of California);
  - `mahzor-vitri-abraham-berliner-1893`, a copy the Open Siddur Project derived from a Google Books scan.

  They are admitted under rule 3 of HeOCR's legal strategy and heocr-engine decision 0015. Google's front matter was excluded, and lines under a "Digitized by Google" watermark were dropped; none was found on the training pages. Each item passed HeOCR's Internet Archive rights gate, and each text aligned to it has its own rights justification, listed by id in the training record and the NOTICE.
- **Text sources:** Project Ben-Yehuda (public domain dump, release 2026-03) for the four books; Sefaria's public-domain digital versions of the 1884 and 1889–97 printings; and Project Gutenberg ebook #43740 (public domain in the USA), produced by David T. Jones, Enrico Segre and Distributed Proofreaders Canada.
- **Reshumot replay:** a seeded sample (seed 20261129) of 40,000 of the 45,250 decontaminated anchor lines of HeOCR's office-print v0 round: lines rendered by HeOCR from born-digital booklets of *Sefer ha-Hukim* and *Kovetz ha-Takanot*, labelled with the publisher's own text layer. The 8% per-book cap left too few P-hist lines to fill a round, so the replay share is high, 52%.
- **Labels:** logical order, NFC, with `׳`→`'`, `״`→`"` and `—`→`–`, so that every label fits R7's character set and matches the scoring profile.
- **Decontamination:** 76 pool lines that shared a word 6-gram with an evaluation target were dropped. HeOCR's evaluation then ran its official overlap check (`check_train_overlap`: word 6-grams after folding, against every evaluation target) on the whole list: **CLEAN, with 0 hits on every target** (2026-11-18). Its page check against the P-hist hold-out found only 5 pages sharing text, and those pages are permanently out of scoring.
- **All authors, editors and named contributors of the books and editions died more than 70 years ago,** per their rights justifications, so the books are in the public domain in Israel. Every book was printed before 1931 and is also past the US term.
- **R7's own training data** (95,151 lines from 7 NLI "public domain, free use" scans and 23 Internet Archive university-library scans, with Project Ben-Yehuda labels) is credited in R7's NOTICE, which ships with this model as `NOTICE.r7`.

### Training procedure

- **Start:** HeOCR R7 (`--continue_from` its LSTM, `--old_traineddata` and `--traineddata` R7). The network and character set are R7's, unchanged.
- **Trainer:** `lstmtraining`, Tesseract 5.5.3 built from its upstream tag (commit `db0ec62f…`), on a 16-vCPU CPU pod, `--learning_rate 0.0001 --reset_learning_rate --target_error_rate 0.01`, one epoch (76,946 iterations), with a snapshot every 10 minutes. The run exited cleanly; the pod checked every input's sha256 before training.
- **Truth order:** labels in Tesseract's LSTM training order, converted with `tesseract … --psm 13 lstm.train`.
- **Selection:** the lowest page CER on audit2 (below) under `line_fold_v1`, over 20 candidates: 8 snapshots, the training-best checkpoint and the final model of this arm and of a second arm started from stock `heb`. The winner is this arm's final model at 16.753%. The stock-start arm's final model was second, 0.061 points behind. Snapshots move by about ±0.4 points, and audit2's 38 pages cannot separate neighbours reliably.
- **One training run.** It is not deterministic, and the bytes are not reproducible.

### Word list

The word list is R7's, unchanged: the model's `lstm-word-dawg` has R7's sha256, `cddcc086c241eeaf0f29b77f7955770d4fe3b2832f8fec986e53c7a0a579fcdb`. Its entries are tessdata_best's 70,171, and none comes from any training text.

## Evaluation

- **No test score.** Every figure is from a development set. The P-hist test (22 held-out books) waits for its human references; HeOCR will score this model on it once, in a registered run, against R7 and stock.
- **Sources:** HeOCR's P-hist round v1 results and evaluation's default-model study (2026-11-19). All figures are aggregates.
- **Scoring profile `line_fold_v1`** (sha256 `2e2627104be4f27dc3204787dd3ff4f8591d95d1d96294c65833d2773041d317`): NFC, whitespace collapsed, and the folds `־`→`-`, `׳`→`'`, `״`→`"`, `“ ” „`→`"`, `—`→`–`.
- **Stock Tesseract** (tessdata_best `heb` at `e12c65a`, the base) is shown beside every figure, read the same way.

### Old-print pages: audit2 (the selection set)

38 page images from 13 old-print books, P-hist dev, read whole at psm 3. Micro page CER %.

| | stock `heb` | R7 (start model) | **oldprint-v1** |
|---|---|---|---|
| audit2 CER | 20.261 | 18.330 | **16.753** |

- **Optimistic:** audit2 chose this model.
- **Against stock:** −3.51 points, 95% interval over books [−6.10, +0.30], which includes 0. R7, which audit2 did not choose, is −1.93 [−4.05, +1.25].
- **Dashes:** audit2's references hold 32 en dashes after folding; R7's character set can write them, stock's cannot.

### Real print, line sets (dev)

Every line of each list read at psm 7 and scored under `line_fold_v1`. Δ is oldprint-v1 − stock, with its 95% paired bootstrap interval over lines (10,000 resamples, seed 0).

| List | Lines | stock `heb` | R7 | **oldprint-v1** | Δ vs stock [95%] |
|---|---|---|---|---|---|
| Scanned Reshumot, OLB dev | 3,254 | 5.428 | 2.934 | **2.209** | −3.220 [−3.330, −3.112] |
| Scanned Reshumot, OLB dev v1.1 | 3,325 | 5.410 | 2.924 | **2.198** | −3.212 [−3.320, −3.104] |
| Reshumot rendered dev | 2,716 | 6.613 | 7.789 | **0.838** | −5.774 [−6.366, −5.264] |
| *Kevar* (1922), held out | 4,600 | 5.677 | **0.850** | 0.948 | −4.729 [−4.843, −4.622] |
| *Yedi'ot ha-Teva* (1883), held out | 4,600 | 9.218 | 1.333 | **1.086** | −8.132 [−8.272, −7.998] |
| Brainin, IA scan | 6,257 | 5.071 | **0.635** | 0.868 | −4.203 [−4.276, −4.130] |
| Brainin, NLI scan | 4,046 | 10.450 | 1.355 | **1.271** | −9.179 [−9.354, −9.004] |
| Silman, *Sansinim* | 3,046 | 5.824 | 1.001 | 1.001 | −4.823 [−4.945, −4.704] |
| Mekhilta (rabbinic) | 3,141 | 7.512 | 1.896 | **1.122** | −6.390 [−6.492, −6.289] |
| Wikisource dev | 257 | 14.672 | 8.030 | **7.233** | −7.439 [−7.883, −7.018] |
| Bodek | 21 | 15.684 | 6.166 | **4.960** | −10.724 [−13.190, −8.739] |
| R8b selection lines | 3,000 | 7.549 | 1.078 | **1.005** | −6.544 [−6.723, −6.371] |

- **Better than stock on every list,** with every interval below 0.
- **Against R7:** better on 9 lists, tied on Silman, and worse on *Kevar* (+0.10) and Brainin's IA scan (+0.23).
- **Modern print kept:** R7 is worse than stock on rendered Reshumot (+1.18 points); the replay turns that into −5.77.
- **Exposure:** R7, and so this model through it, trained on other lines of some of these books; Silman and the NLI Brainin scan chose R7's checkpoints. These lists show that nothing is lost; they are not an out-of-domain claim.
- ***Yedi'ot ha-Teva*** has a known label error rate (3 word errors in 32 audited lines), so its figure is reported but weighs less.

### HeOCR's open synthetic document sets, inside heocr (tuning)

Page CER %, with missed numbers % in brackets, heocr at `1b53753`. These open synthetic office sets are what modern-v1 is for; they show where not to use this model.

| Cell | heocr with stock `heb` | heocr with oldprint-v1 | upper bound of the difference |
|---|---|---|---|
| Scanned PDF under a wrong text layer (T4) | **2.87** (20.0) | 3.92 (12.5) | CER +1.74 |
| Image-only PDF (T5) | **4.22** (13.2) | 5.13 (11.8) | CER +1.30 |
| Scanned tables | **1.58** (2.59) | 2.89 (2.14) | CER +1.62 |
| Correct OCR layer kept (T6) | **0.12** (0.22) | 0.15 (0.06) | |

- **Worse on CER in every OCR cell,** though it misses fewer numbers than stock in each.
- **Grainy JPEG tables (stress set):** CER 14.02% against 12.24% with stock inside, and it keeps 8.1% of faint text outside the table, against stock's 29.7%.
- **Numbers on 42 synthetic office scans:** 155 gained and 316 lost against stock.
- **Development PDFs (reference-free):** dictionary-hit rate 80.30% against stock's 80.20% (+0.09 [−0.03, +0.33]); no veto fires.

## Bias, risks and limitations

- **No test score.** audit2 chose the model, and the line sets are dev.
- **Worse than stock on modern office documents** inside heocr. Route modern print to modern-v1.
- **Training data:** 7 books and editions printed between 1881 and 1923, plus R7's 30 books (1856–1938), and modern Reshumot replay (52% of this round). Other typefaces, layouts and periods may gain less, or lose.
- **Regressions against R7** on two scans: *Kevar* and Brainin's Internet Archive copy, small, dark and grainy.
- **Square type only.** Not for Rashi script, handwriting or Latin text.
- **No niqqud training.**
- **Edition spelling.** The text sources sometimes modernise or vary the spelling of the print, and the labels carry those variants.
- **Layout is Tesseract's,** or heocr's when used inside heocr.
- **One training run.** The intervals cover sampling, not training seeds.

## Related models

- **HeOCR modern-v1** (`heocr_modern_v1`): the same release round, for modern print and office documents. It is heocr's default model.
- **HeOCR R7:** the model this one continues from. R7's card, record and deposit are unchanged.
- **HeOCR R8b:** a separate continuation of R7 for modern print. oldprint-v1 is not derived from it.

## Licence and attribution

- **Licence:** Apache-2.0. Copyright (c) 2026 HeOCR maintainers.
- **Base model:** a modified (fine-tuned) version of tessdata_best `heb`, Apache-2.0, from the Tesseract OCR project, through HeOCR R7.
- **NOTICE and NOTICE.r7:** redistributions must keep both. They credit:
  - the tessdata_best base model and the langdata_lstm build files;
  - the National Library of Israel (through R7): From the collections of the National Library of Israel / מאוסף הספרייה הלאומית;
  - the Internet Archive and the contributing libraries, with every identifier; the original conditions of each item on the Internet Archive still apply;
  - the Google-class scans retrieved via the Internet Archive, with their hygiene and the decisions that admit them;
  - Reshumot, the official gazette of the State of Israel;
  - Project Ben-Yehuda volunteers, Sefaria, and Project Gutenberg's producers for the texts.
- **No endorsement.** Neither the National Library of Israel, the Internet Archive, Google, the Open Siddur Project, the contributing libraries, Reshumot or the State of Israel, Project Ben-Yehuda, Sefaria, Project Gutenberg nor the Tesseract project endorses HeOCR or this model.
- **The model contains no scan images or text files.**

## Provenance and reproduction

| Part | Identity |
|---|---|
| Base model | tessdata_best `heb.traineddata` at `e12c65a915945e4c28e237a9b52bc4a8f39a0cec`, sha256 `dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5` |
| Continued from | HeOCR R7, `heocr_r7.traineddata`, sha256 `95faab81fba6fe57…` |
| Training list | `phist_r7.list`, sha256 `0cd3e7e8…`; labels `bbdaade0…`; inputs manifest `250de59de77f6fd1353d68f2ddb88b5a4858ed33855a536429d67f1993b8733e` |
| Line sets | `bynli_lines_v3` (manifest sha256 `4cba250f…`), `rablines_v1` (`8583cf41…`), office-print v0 anchor (`lists_v2`); pool `phist_pool_v1` |
| Text | Project Ben-Yehuda `public_domain_dump`, release 2026-03; Sefaria public-domain versions; Project Gutenberg #43740 |
| Training | Tesseract 5.5.3 `lstmtraining`, 2026-11-18, run `20261118-175353-bdbd`; selected checkpoint `heb_final` |
| Records | hocrsyngen `experiments/phist_v1/` (REGISTRATION.md, RESULTS.md); evaluation's default-model study report |
| Training record | `oldprint_v1_training_run.json`, in this deposit |

## Contact

Report problems and questions as issues on [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine/issues). A rights concern can be raised the same way, or by email to heocrproject@gmail.com; name the Internet Archive identifier, the Reshumot booklet or the text source. The takedown procedure is at [heocr.github.io/rights.html](https://heocr.github.io/rights.html).

## Citation

Cite this model by its version DOI: [10.5281/zenodo.24371759](https://doi.org/10.5281/zenodo.24371759).
