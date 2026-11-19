# HeOCR R6: Hebrew printed-text recognition for Tesseract

R6 is a [Tesseract](https://github.com/tesseract-ocr/tesseract) language model (`.traineddata`) for printed modern Hebrew. HeOCR made it by fine-tuning Tesseract's own `heb` model from [tessdata_best](https://github.com/tesseract-ocr/tessdata_best) on 13,648 real scanned lines. The lines come from public-domain books in the National Library of Israel's "public domain, free use" collection. Each line is labelled with the Project Ben-Yehuda transcription of the same edition, never with OCR output.

It is a fine-tuned Tesseract model for printed Hebrew pages, not a new engine.

**Performance: not measured on a held-out set yet.** HeOCR reports accuracy only on held-out sets, and this model has not yet been scored on one. No held-out score yet; HeOCR will score it once in a registered held-out run. Its result will be added to this card in a new version.

- **How it was chosen:** its checkpoint was picked on two held-out-from-training books (the selection lines, see [Training procedure](#training-procedure-and-hyperparameters)). It was then compared with stock Tesseract on real printed development pages (E2d4c). These sets were used to choose and compare it, so they are not reported here as its performance.
- **No gain on the hardest development pages.** Check the output.

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
- **Unsupervised transcription.** It still makes many errors on real pages. Check the output.
- **Documents that are not mainly Hebrew.** No Latin text was in the training lines.

## How to get started with the model

Install Tesseract 4 or 5 (tested with 5.5.3). Put `heocr_r6.traineddata` in a directory, say `DIR`, and pass that directory and the language name `heocr_r6`.

**Whole pages: page segmentation mode 3** (automatic layout, Tesseract's default). HeOCR compared it on pages in this mode.

```sh
tesseract page.png out -l heocr_r6 --tessdata-dir DIR --psm 3
```

This writes `out.txt`, in logical (reading) order.

**Single line images: psm 13** (raw line). Do not use psm 7 on line crops. On crops that carry a sliver of the neighbouring line, psm 7 returns empty text, with stock `heb` and with R6 alike: this happened on many lines of one of the selection books.

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
- **Selection:** the checkpoint with the lowest character error (BCER, `lstmeval`) on the selection lines, over all 96 saved checkpoints of both arms. That is `lrdef` at iteration 54,500 (`heb_0.603_16919_54500`). The selection lines chose the checkpoint, so their scores are not reported as performance. The `lr1e4` arm was not chosen.
- **Conversion:** `lstmtraining --stop_training` to `heb.traineddata`, renamed `heocr_r6.traineddata` for release (same bytes).
- **One training run.** It is not deterministic, and the bytes are not reproducible.

## Evaluation

**Not measured on a held-out set yet.** HeOCR reports a model's accuracy only on sets held out from its training, selection and tuning. No held-out score yet; HeOCR will score it once in a registered held-out run.

- **What was used to choose it is not reported as performance.** The selection lines (Silman and Brainin, read one crop at a time) chose the checkpoint. The E2d4c pages (38 real printed Hebrew pages from 14 Hebrew Wikisource Indexes, human-adjudicated references, hocrgen manifest `e2d4c_wikisource_printed_v7`) and their earlier version E2d3d compared it with stock Tesseract and with its base. They count as development sets.
- **What the development comparison showed, in words:** R6 read the development pages better than stock Tesseract on average, but not every page, and it showed no gain on the hardest development pages, whose Wikisource Indexes fed none of HeOCR's glyph banks. Almost all of R6's training lines come from three books, which is the likely reason. It drops more characters than stock does, so deletions are part of its error. Its remaining line errors are mostly letter confusions: כ/ב, ד/ר, ג/נ, י/ו and ס/ם.
- **No text overlap with training.** The training labels share no word 6-gram with the E2d4c reference texts (letters only, niqqud stripped). The full Ben-Yehuda texts of the five training books share none either, except three 6-grams from two Bible verses (Isaiah 26:2, Psalms 118:20) that one Frank story and one development page both quote. No evaluation manifest names an NLI record.
- **Next:** HeOCR's registered held-out run, against stock Tesseract `heb` and tessdata_best `heb` (the base), shown beside it and read the same way. Its result will be added in a new version of this card.

## Bias, risks and limitations

- **Not measured on a held-out set yet.** See [Evaluation](#evaluation). On the development pages it was better than stock Tesseract on average, made some pages worse, and showed no gain on the hardest ones.
- **Narrow training data.** Nearly all the lines come from three books, printed in Warsaw, Vilna and Jerusalem between 1910 and 1927. Other typefaces, layouts and periods may gain less, or lose.
- **Printed Hebrew only.** Not for handwriting, Rashi script or non-Hebrew text.
- **No niqqud training.** The labels have no vowel points; pointed text was not evaluated.
- **Edition spelling.** Ben-Yehuda sometimes modernises or varies the spelling of the print, and the labels carry those variants. R6 may sometimes write the edition's spelling instead of the printed one.
- **Layout is Tesseract's.** R6 changes only the line recognizer. Page segmentation and reading order are Tesseract's own, and on complex layouts they dominate the error.
- **One training run.** It was trained once, with one seed; how much another run would differ is not known.

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
| Development comparison | hocrgen `d4a3414` `evaluate-references`, `primary.v1`, Tesseract 5.5.3 psm 3; development references `e2d4c_wikisource_printed_v7` (manifest sha256 `0de65f63…`) |

The line set is not yet published. Its per-line manifest names each line's NLI record, canvas, box and Ben-Yehuda work, so the training set can be rebuilt from the public scans and texts, or rebuilt without any one book.

## Contact

Report problems and questions as issues on [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine/issues). A rights concern about any source book can be raised the same way, or by email to heocrproject@gmail.com; name the NLI record id. The takedown procedure is at [heocr.github.io/rights.html](https://heocr.github.io/rights.html).

## Citation

Cite this model by its version DOI: [10.5281/zenodo.24372342](https://doi.org/10.5281/zenodo.24372342).
