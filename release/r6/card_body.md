# HeOCR R6: Hebrew printed-text recognition for Tesseract

R6 is a [Tesseract](https://github.com/tesseract-ocr/tesseract) language model (`.traineddata`) for printed modern Hebrew. HeOCR made it by fine-tuning Tesseract's own `heb` model from [tessdata_best](https://github.com/tesseract-ocr/tessdata_best) on 13,648 real scanned lines. The lines come from public-domain books in the National Library of Israel's "public domain, free use" collection. Each line is labelled with the Project Ben-Yehuda transcription of the same edition, never with OCR output.

It is a small, measured improvement on stock Tesseract for printed Hebrew pages, not a new engine. On 38 real printed pages with human-adjudicated references it lowers the character error rate (CER) from 0.226 to 0.209. On the 10 hardest of those pages it gains nothing (see [Evaluation](#evaluation)).

It is released on its own, with no link to HeOCR's kraken pipeline (R4d, A1, R3h).

| | |
|---|---|
| File | `heocr_r6.traineddata` (trained as `heb.traineddata`), 3,628,595 bytes |
| sha256 | `73eb18e03f8793dff9c03699db0845779f6b5db4897824bcd61787245ec66e10` |
| Model type | recognition (line-level LSTM, CTC); Tesseract does the page layout |
| Format | Tesseract 4/5 LSTM `traineddata`, LSTM only (`--oem 1`; no legacy engine). Trained and tested with Tesseract 5.5.3 |
| Base model | tessdata_best `heb.traineddata` at [`e12c65a`](https://github.com/tesseract-ocr/tessdata_best/tree/e12c65a915945e4c28e237a9b52bc4a8f39a0cec) (Apache-2.0), sha256 `dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5`, fine-tuned (modified) by HeOCR |
| Licence | Apache-2.0, Copyright (c) 2026 HeOCR maintainers (see LICENSE and NOTICE) |
| Training record | `r6_training_run.json` (`heocr_tesseract_training_run.v1`) |
| Code | [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine) |

## Uses

- **OCR of printed Hebrew pages,** books and periodicals in the square script, such as early-20th-century book type, without niqqud. Use it in place of Tesseract's `heb`.
- **Line recognition** of single printed Hebrew line images, for example lines found by another segmenter.
- **A research baseline** for Hebrew OCR on real scans.

### Out of scope

- **Handwriting.** R6 was trained on print only.
- **Niqqud (vowel points) and cantillation.** The training labels have none (see [Training data](#training-data)). How R6 behaves on pointed text was not measured.
- **Rashi script and other non-square Hebrew scripts,** and medieval or other historical hands.
- **Unsupervised transcription.** Its CER on real pages is still about 0.21 (one character in five). Check the output.
- **Documents that are not mainly Hebrew.** No Latin text was in the training lines.

## How to get started with the model

Install Tesseract 4 or 5 (tested with 5.5.3). Put `heocr_r6.traineddata` in a directory, say `DIR`, and pass that directory and the language name `heocr_r6`.

**Whole pages: page segmentation mode 3** (automatic layout, Tesseract's default). The page figures below use it.

```sh
tesseract page.png out -l heocr_r6 --tessdata-dir DIR --psm 3
```

This writes `out.txt`, in logical (reading) order.

**Single line images: psm 13** (raw line). Do not use psm 7 on line crops. On crops that carry a sliver of the neighbouring line, psm 7 returns empty text, with stock `heb` and with R6 alike: this happened on 473 of 4,046 lines of one held-out book.

```sh
tesseract line.png out -l heocr_r6 --tessdata-dir DIR --psm 13
```

Notes:
- **`--tessdata-dir` replaces Tesseract's data directory.** Output formats other than plain text (`tsv`, `hocr`, `pdf`, `alto`) read their config files from `DIR/configs`. Link or copy the `configs` folder of your Tesseract installation into `DIR`, or put `heocr_r6.traineddata` in your installation's own tessdata directory and drop `--tessdata-dir`.
- **The language name is the file name without `.traineddata`.** `heocr_r6` follows tessdata's naming (`chi_sim`, `deu_latf`). It combines with other models in the usual way, for example `-l heocr_r6+eng`, which runs but was not evaluated.

## Training details

### Training data

**Lines:** 13,648 real line images, the train split of HeOCR's `bynli_lines_v1` line set (Ben-Yehuda × NLI). They were cut from NLI scans of five books, in which 99.9% of the lines come from three:

| NLI record | Book | Lines |
|---|---|---|
| [990020308000205171](https://iiif.nli.org.il/IIIFv21/990020308000205171/manifest) | Yeshayahu Berashadsky (1871–1908), *Ketavim Aharonim*, Warsaw: Tushiya, 1910 | 6,076 |
| [990020495520205171](https://iiif.nli.org.il/IIIFv21/990020495520205171/manifest) | Shmuel Leib Citron (1860–1930), *Me-Ahorei ha-Pargod*, Vilna: Z. Matz, 1923–1925 | 6,052 |
| [990020522850205171](https://iiif.nli.org.il/IIIFv21/990020522850205171/manifest) | Shmuel Tchernowitz (1879–1929), *Im Shahar*, Jerusalem: Ha-Madpis, 1927 | 1,511 |
| [990019385920205171](https://iiif.nli.org.il/IIIFv21/990019385920205171/manifest) | Azriel Natan Frank (1863–1924), *Sefer Agadot ha-Zohar*, Warsaw: Ahiasaf, 1923–1924 | 8 |
| [990013538860205171](https://iiif.nli.org.il/IIIFv21/990013538860205171/manifest) | Yitzhak Katzenelson (1885–1944), *Shirim*, Lodz: Hovevei Shira, 1938 | 1 |

- **Scans:** From the collections of the National Library of Israel / מאוסף הספרייה הלאומית. Each record's IIIF manifest carries NLI's "public domain, free use" licence. They were fetched from NLI's IIIF service. No Google-digitized "non-commercial use" scan was used.
- **Text:** the Project Ben-Yehuda public-domain transcription of the same edition (public domain dump, release 2026-03), placed on each scanned line by HeOCR's alignment tool (hocrgen F8f). Lines were kept only where the alignment scored at least 0.9 and its text agreed with Tesseract's reading of the line at a similarity of at least 0.7. Tesseract only located the lines and chose between candidate spans at a line's edges; **no label is OCR output.**
- **Label normalisation:** Unicode NFC, logical order. Niqqud removed; `…` written as `...`, `„` as `"`, soft hyphens removed. The training labels contain no niqqud and no Latin letters; 90 of them contain digits.
- **Pointed prints dropped:** two fully pointed books (*Mahamadim*, Mandelkern) were left out. *Shirim* keeps one short line, with its niqqud removed.
- **Edition spelling:** Ben-Yehuda's text sometimes differs from the print (for example אתה for a printed אותה). Such variants are in the labels; Tchernowitz has the most, at 5.7% of words.
- **All authors died more than 70 years ago,** so the books are in the public domain in Israel. The four books printed before 1931 are also past the US term. *Shirim* (1938, one line) has no established US status.

**Selection lines (not trained on):** 7,092 lines of two further NLI "public domain, free use" books, held out whole: Kadish Yehuda Silman (1880–1937), *Sansinim*, Tarbut, 1929 ([990020250940205171](https://iiif.nli.org.il/IIIFv21/990020250940205171/manifest), 3,046 lines), and Reuven Brainin (1862–1939), *Avraham Mapu: Hayav u-Sfarav*, Tushiya, 1928 ([990018546440205171](https://iiif.nli.org.il/IIIFv21/990018546440205171/manifest), 4,046 lines).

### Training procedure and hyperparameters

- **Start:** tessdata_best `heb` (`e12c65a`), its LSTM extracted with `combine_tessdata`. The network is the base's own, unchanged: `[1,36,0,1Ct3,3,16Mp3,3Lfys48Lfx96Lrx96Lfx192O1c1]`.
- **Character set:** the base's, plus the maqaf `־` and the en dash `–`. The output layer grew from 69 to 70 codes. The dictionary is the base's own word list, rebuilt with Tesseract's build files from [langdata_lstm](https://github.com/tesseract-ocr/langdata_lstm) `07930fd` (Apache-2.0).
- **Truth order:** each label is written in Tesseract's LSTM training order: the logical line reversed, punctuation not mirrored, digit runs kept left to right. Each line was converted to `.lstmf` with `tesseract … --psm 13 lstm.train`.
- **Trainer:** `lstmtraining --continue_from` the base, Tesseract 5.5.3, on CPU. Two arms of 100,000 iterations each (`--target_error_rate 0.01`):
  - `lrdef`: the learning rate stored in the base, not set on the command line;
  - `lr1e4`: `--learning_rate 0.0001 --reset_learning_rate`.
- **Selection:** the checkpoint with the lowest BCER (`lstmeval`) on the selection lines, over all 96 saved checkpoints of both arms. That is `lrdef` at iteration 54,500 (`heb_0.603_16919_54500`): BCER 2.03%, BWER 5.30%. On the same lines tessdata_best scores 11.45% / 23.34%. The best `lr1e4` checkpoint scored 2.14% / 5.81%.
- **Conversion:** `lstmtraining --stop_training` to `heb.traineddata`, renamed `heocr_r6.traineddata` for release (same bytes).
- **One training run.** It is not deterministic, and the bytes are not reproducible.

## Evaluation

### Real pages

- **Testing data:** E2d4c, 38 real printed Hebrew pages from 14 Hebrew Wikisource Indexes, with human-adjudicated references (hocrgen manifest `e2d4c_wikisource_printed_v7`). They are a scored set under heocr-engine decision 0012: no training, tuning or checkpoint choice used them, R6 was scored on them once after selection, and their works are held out of training.
- **Metric:** CER and WER under hocrgen's `primary.v1` normalisation (hocrgen `d4a3414` `evaluate-references`), pooled over pages. Every engine reads whole pages with Tesseract 5.5.3, psm 3.
- **Intervals:** 95% paired bootstrap against stock Tesseract, resampling pages, then Wikisource Indexes (clusters); 2,000 resamples, seed 20261106.

| Engine | CER, 38 pages | WER, 38 pages | CER, 10 pages | WER, 10 pages |
|---|---|---|---|---|
| Stock Tesseract `heb` (Homebrew) | 0.226 | 0.473 | 0.384 | 0.588 |
| tessdata_best `heb` (R6's base) | 0.225 | 0.481 | 0.376 | 0.609 |
| **R6** | **0.209** | **0.407** | 0.383 | 0.585 |

| R6 minus | ΔCER, 38 pages (page; cluster) | ΔCER, 10 pages (page; cluster) |
|---|---|---|
| stock Tesseract | **−0.016 [−0.023, −0.010]**; cl [−0.024, −0.005] | −0.002 [−0.012, +0.012]; cl [−0.006, +0.002] |
| tessdata_best | −0.015 [−0.024, −0.007]; cl [−0.026, +0.001] | +0.007 [−0.006, +0.018]; cl [−0.005, +0.019] |

- **On the 38 pages,** R6 lowers CER by 0.016 and WER by 0.066 [−0.086, −0.046] against stock Tesseract. It improves 26 pages, leaves 2 unchanged and worsens 10.
- **No gain on the hardest pages.** The 10-page subset is the pages whose Wikisource Indexes fed none of HeOCR's glyph banks. Stock Tesseract's error is highest there, and R6 is level with it (0.383 against 0.384). Almost all of R6's training lines come from three books, which is the likely reason.
- **Against its own base,** the page interval excludes zero on the 38 pages, but the cluster interval just reaches it (+0.001).
- **What is left is recognition, not reading order.** An order-free character-bag error is 0.215 for R6 (stock: 0.238), about the same as its CER. R6 emits about 7% fewer characters than the references (stock: about 3%), so deletions are part of its error.
- **Reference caveat:** E2d4c is the human audit of the earlier E2d3d references. Some audit proposals came from places where Tesseract and another engine agreed with each other but not with the reference, so the corrections may lean slightly toward what Tesseract reads. That is why every comparison above is paired on the same references. On the pre-audit references (`e2d3d_wikisource_printed_v5`) R6 scores 0.219 against stock's 0.237; R6 − stock is −0.017 [−0.024, −0.011].
- **No text overlap with training.** The 13,648 training labels share no word 6-gram with the 38 reference texts (letters only, niqqud stripped). The full Ben-Yehuda texts of the five training books share none either, except three 6-grams from two Bible verses (Isaiah 26:2, Psalms 118:20) that one Frank story and one evaluation page both quote. No evaluation manifest names an NLI record.

### Line crops

On the 7,092 selection lines (Silman and Brainin), read one crop at a time with psm 13 and scored with hocrgen:

| Engine | Exact lines | CER |
|---|---|---|
| Stock Tesseract `heb` | 13.0% | 5.98% |
| R6 | 69.5% | 1.25% |

These lines chose R6's checkpoint, and the line set kept only lines whose text agreed with stock Tesseract's reading at 0.7 or more. So the figures are optimistic, and they compare engines rather than give an absolute level. R6's remaining line errors are mostly letter confusions: כ/ב, ד/ר, ג/נ, י/ו and ס/ם.

## Bias, risks and limitations

- **A small gain.** R6 is better than stock Tesseract on average, by 0.016 CER, and is no better on the hardest pages. It worsens 10 of 38 pages.
- **Narrow training data.** 99.9% of the lines come from three books, printed in Warsaw, Vilna and Jerusalem between 1910 and 1927. Other typefaces, layouts and periods may gain less, or lose.
- **Printed Hebrew only.** Not for handwriting, Rashi script or non-Hebrew text.
- **No niqqud training.** The labels have no vowel points; pointed text was not evaluated.
- **Edition spelling.** Ben-Yehuda sometimes modernises or varies the spelling of the print, and the labels carry those variants. R6 may sometimes write the edition's spelling instead of the printed one.
- **Layout is Tesseract's.** R6 changes only the line recognizer. Page segmentation and reading order are Tesseract's own, and on complex layouts they dominate the error.
- **One training run, small evaluation.** The intervals cover page and Index sampling, not training seeds. 38 pages from 14 Indexes is a small scored set.

## Licence and attribution

- **Licence:** Apache-2.0. Copyright (c) 2026 HeOCR maintainers.
- **Base model:** a modified (fine-tuned) version of tessdata_best `heb`, Apache-2.0, from the Tesseract OCR project.
- **NOTICE:** redistributions must keep the NOTICE file. It credits:
  - the tessdata_best base model and the langdata_lstm build files (Apache-2.0);
  - the National Library of Israel for the scans, with every record id: From the collections of the National Library of Israel / מאוסף הספרייה הלאומית;
  - Project Ben-Yehuda volunteers for the text;
  - Hebrew Wikisource, whose CC BY-SA transcriptions were used for scoring only, never for training.
- **No endorsement.** Neither the National Library of Israel, Project Ben-Yehuda, the Tesseract project nor Wikisource endorses HeOCR or this model.
- **The model contains no scan images or text files.** The line crops are not distributed with it.

## Provenance and reproduction

| Part | Identity |
|---|---|
| Base model | tessdata_best `heb.traineddata` at `e12c65a915945e4c28e237a9b52bc4a8f39a0cec`, git blob `0fc27335…`, sha256 `dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5` |
| Starter | base character set plus `־` and `–`, the base's word list, langdata_lstm `07930fd`; `heb.traineddata` sha256 `8b9d798a456bd1d4cd8bdf71b3d7b9d7579cea6cbd51302accd57f521669b846` |
| Line set | `bynli_lines_v1` (schema `s16c_benyehuda_nli_lines.v1`): `manifest.jsonl` sha256 `9b6adb4253954aa164dc699bc647abb416611792aa5bfb06737cf3f00155dc72`, `summary.json` `82c2756bafd9327f9a392719d0a7e55e71e0f62912d039d84dbb5ae3567dce46`; its 20,740 PNGs concatenated in sorted path order `a1484332598d1f4a3ec8fdef0bf4f2f8cc7abcdf952ef5dd9bde26ca93503cb8`. Built with hocrgen's canvas-to-image fix (`fc1a524`) |
| Text | Project Ben-Yehuda `public_domain_dump`, release 2026-03 |
| Training | Tesseract 5.5.3 `lstmtraining` (Homebrew), 2026-11-09; selected checkpoint `lrdef/heb_0.603_16919_54500` |
| Training record | `r6_training_run.json` (`heocr_tesseract_training_run.v1`), in this deposit |
| Scoring | hocrgen `d4a3414` `evaluate-references`, `primary.v1`, Tesseract 5.5.3 psm 3; references `e2d4c_wikisource_printed_v7` (manifest sha256 `0de65f63…`) |

The line set is not yet published. Its per-line manifest names each line's NLI record, canvas, box and Ben-Yehuda work, so the training set can be rebuilt from the public scans and texts, or rebuilt without any one book.

## Contact

Report problems and questions as issues on [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine/issues). A rights concern about any source book can be raised the same way, or by email to heocrproject@gmail.com; name the NLI record id. The takedown procedure is at [heocr.github.io/rights.html](https://heocr.github.io/rights.html).

## Citation

Cite this model by its version DOI. <!-- DRAFT: R6's reserved version DOI (release/README.md, R6 plan step 2). Never cite the concept DOI. -->
