# HeOCR R7: Hebrew printed-text recognition for Tesseract

R7 is a [Tesseract](https://github.com/tesseract-ocr/tesseract) language model (`.traineddata`) for printed modern Hebrew. HeOCR made it by fine-tuning Tesseract's own `heb` model from [tessdata_best](https://github.com/tesseract-ocr/tessdata_best) on 95,151 real scanned lines from 30 public-domain books. Seven of the books are National Library of Israel "public domain, free use" scans; 23 are university-library scans from the Internet Archive. Each line is labelled with the Project Ben-Yehuda transcription of the same edition, never with OCR output.

It has the same recipe and the same base as [HeOCR R6](https://doi.org/10.5281/zenodo.24109989), on about seven times as many lines from six times as many books. It does not continue from R6.

**What it gains, and what it does not.** R7 is better than stock Tesseract on printed Hebrew pages, but no better than R6:
- On 38 real printed pages with human-adjudicated references, it lowers the character error rate (CER) from 0.226 (stock) to 0.209, and the word error rate (WER) from 0.473 to 0.393.
- Against R6 it is a tie on CER (0.2089 against 0.2094; R7 − R6 = −0.0005 [−0.0072, +0.0061]). Its WER is slightly lower, but the interval includes zero.
- On the 10 hardest of those pages it is no better than stock Tesseract or R6, and its CER point estimate is slightly worse (see [Evaluation](#evaluation)).

**R7 supersedes nothing. R6 remains valid.** Use R7 if you want the newer model trained on more varied books; it has no measured page-level gain over R6.

It is released on its own, with no link to HeOCR's kraken pipeline (R4d, A1, R3h).

| | |
|---|---|
| File | `heocr_r7.traineddata` (trained as `heb.traineddata`), 3,628,595 bytes |
| sha256 | `95faab81fba6fe57f854f973c1ccad2b0d1059fb951f34b17277385ceea8b303` |
| Model type | recognition (line-level LSTM, CTC); Tesseract does the page layout |
| Format | Tesseract 4/5 LSTM `traineddata`, LSTM only (`--oem 1`; no legacy engine). Trained and tested with Tesseract 5.5.3 |
| Base model | tessdata_best `heb.traineddata` at [`e12c65a`](https://github.com/tesseract-ocr/tessdata_best/tree/e12c65a915945e4c28e237a9b52bc4a8f39a0cec) (Apache-2.0), sha256 `dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5`, fine-tuned (modified) by HeOCR |
| Licence | Apache-2.0, Copyright (c) 2026 HeOCR maintainers (see LICENSE and NOTICE) |
| Training record | `r7_training_run.json` (`heocr_tesseract_training_run.v1`) |
| Code | [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine) |

## Uses

- **OCR of printed Hebrew pages,** books and periodicals in the square script, such as 19th- and early-20th-century book type, without niqqud. Use it in place of Tesseract's `heb`.
- **Line recognition** of single printed Hebrew line images, for example lines found by another segmenter.
- **A research baseline** for Hebrew OCR on real scans, and for comparison with R6: the two differ only in their training lines.

### Out of scope

- **Handwriting.** R7 was trained on print only.
- **Niqqud (vowel points) and cantillation.** The training labels have none, and fully pointed books were left out (see [Training data](#training-data)). How R7 behaves on pointed text was not measured.
- **Rashi script and other non-square Hebrew scripts,** and medieval or other historical hands.
- **Unsupervised transcription.** Its CER on real pages is still about 0.21 (one character in five). Check the output.
- **Documents that are not mainly Hebrew.** No Latin text was in the training lines.

## How to get started with the model

Install Tesseract 4 or 5 (tested with 5.5.3). Put `heocr_r7.traineddata` in a directory, say `DIR`, and pass that directory and the language name `heocr_r7`.

**Whole pages: page segmentation mode 3** (automatic layout, Tesseract's default). The page figures below use it.

```sh
tesseract page.png out -l heocr_r7 --tessdata-dir DIR --psm 3
```

This writes `out.txt`, in logical (reading) order.

**Single line images: psm 13** (raw line). Do not use psm 7 on line crops: with stock `heb` and with R6, psm 7 returned empty text on crops that carry a sliver of the neighbouring line. R7 has the same recognizer and was not tested separately for this.

```sh
tesseract line.png out -l heocr_r7 --tessdata-dir DIR --psm 13
```

Notes:
- **`--tessdata-dir` replaces Tesseract's data directory.** Output formats other than plain text (`tsv`, `hocr`, `pdf`, `alto`) read their config files from `DIR/configs`. Link or copy the `configs` folder of your Tesseract installation into `DIR`, or put `heocr_r7.traineddata` in your installation's own tessdata directory and drop `--tessdata-dir`.
- **The language name is the file name without `.traineddata`.** `heocr_r7` follows tessdata's naming (`chi_sim`, `deu_latf`). It combines with other models in the usual way, for example `-l heocr_r7+eng`, which runs but was not evaluated.

## Training details

### Training data

**Lines:** 95,151 real line images, the train split of HeOCR's `bynli_lines_v2` line set (Ben-Yehuda × NLI and Internet Archive), after two filters (below). They come from 30 books: 19,820 lines from 7 NLI scans and 75,331 from 23 Internet Archive scans. Each record is capped at 6,100 lines, so no book has more than 6.4% of the lines; Smolenskin's collected works, three Internet Archive volumes, have 18.6% together.

| Source | Record | Book | Lines |
|---|---|---|---|
| NLI | [990017640460205171](https://iiif.nli.org.il/IIIFv21/990017640460205171/manifest) | Leo Tolstoy (1828–1910), *Anna Karenina*, Hebrew translation by Yosef Eliyahu Triwosch (1855–1940), Moscow: A. Y. Stybel, 1918–1922 | 6,100 |
| NLI | [990020308000205171](https://iiif.nli.org.il/IIIFv21/990020308000205171/manifest) | Yeshayahu Berashadsky (1871–1908), *Ketavim Aharonim*, Warsaw: Tushiya, 1910 | 6,076 |
| NLI | [990020495520205171](https://iiif.nli.org.il/IIIFv21/990020495520205171/manifest) | Shmuel Leib Citron (1860–1930), *Me-Ahorei ha-Pargod*, Vilna: Z. Matz, 1923–1925 | 6,052 |
| NLI | [990020522850205171](https://iiif.nli.org.il/IIIFv21/990020522850205171/manifest) | Shmuel Tchernowitz (1879–1929), *Im Shahar*, Jerusalem: Ha-Madpis, 1927 | 1,511 |
| NLI | [990020466440205171](https://iiif.nli.org.il/IIIFv21/990020466440205171/manifest) | David Frischmann (1859–1922), *Be-Yom ha-Kippurim*, Warsaw: Y. Alapin, 1881 | 72 |
| NLI | [990019385920205171](https://iiif.nli.org.il/IIIFv21/990019385920205171/manifest) | Azriel Natan Frank (1863–1924), *Sefer Agadot ha-Zohar*, Warsaw: Ahiasaf, 1923–1924 | 8 |
| NLI | [990013538860205171](https://iiif.nli.org.il/IIIFv21/990013538860205171/manifest) | Yitzhak Katzenelson (1885–1944), *Shirim*, Lodz: Hovevei Shira, 1938 | 1 |
| IA | [kolsifreperetsbe03smoluoft](https://archive.org/details/kolsifreperetsbe03smoluoft) | Peretz Smolenskin (d. 1885), *Kol Sifre*, vol. 3, Vilna: M. Katzenellenbogen, 1905 | 6,100 |
| IA | [sifrehazikhronot00mont](https://archive.org/details/sifrehazikhronot00mont) | Israel Hayyim Tavyov (d. 1920), *Sifre ha-Zikhronot le-Sir Moshe Montefiore*, Warsaw: Tushiya, 1898 | 6,100 |
| IA | [kolsifreperetsbe01smoluoft](https://archive.org/details/kolsifreperetsbe01smoluoft) | Peretz Smolenskin (d. 1885), *Kol Sifre*, vol. 1, Vilna: M. Katzenellenbogen, 1905 | 6,096 |
| IA | [kolsifreperetsbe05smoluoft](https://archive.org/details/kolsifreperetsbe05smoluoft) | Peretz Smolenskin (d. 1885), *Kol Sifre*, vol. 5, Vilna: M. Katzenellenbogen, 1905 | 5,489 |
| IA | [miyarketetevel008800](https://archive.org/details/miyarketetevel008800) | Zvi Kasdai (d. 1937), *Mi-Yarkete Tevel*, Jerusalem: A. M. Luncz, 1914 | 4,760 |
| IA | [ldpd_15772050_000](https://archive.org/details/ldpd_15772050_000) | Ludwig Philippson (d. 1889), *Ya'akov Tirado*, translated by Samuel Joseph Fuenn (d. 1891), Vilna: S. Y. Fuenn, 1881 | 4,639 |
| IA | [mabeothayehudims00raff](https://archive.org/details/mabeothayehudims00raff) | Samuel Raffaeli (d. 1923), *Matbe'ot ha-Yehudim*, Jerusalem: E. Dainard, 1913 | 4,135 |
| IA | [atn3681.0001.001.umich.edu](https://archive.org/details/atn3681.0001.001.umich.edu) | Menahem Mendel Dolitzky (d. 1931), *Shevet Sofer*, Vienna: G. Brag, 1883 | 4,027 |
| IA | [maloketravseadya00bornuoft](https://archive.org/details/maloketravseadya00bornuoft) | Hayyim Yehiel Bornstein (d. 1928), *Mahloket Rav Sa'adyah Ga'on u-Ben Meir*, Warsaw: Schuldberg, 1904 | 3,643 |
| IA | [mimitsrayimhusef00fran](https://archive.org/details/mimitsrayimhusef00fran) | Ludwig August Frankl (d. 1894), *Mi-Mitsrayim*, translated by Abraham Baer Gottlober (d. 1899) and Meir Halevi Letteris (d. 1871), Vienna: J. Holzwarth, 1862 | 3,529 |
| IA | [ademataidibruivr00benyuoft](https://archive.org/details/ademataidibruivr00benyuoft) | Eliezer Ben-Yehuda (d. 1922), *Ad Ematai Dibru Ivrit?*, New York: Kadima, 1919 | 2,980 |
| IA | [agadothatanaim11bach](https://archive.org/details/agadothatanaim11bach) | Wilhelm Bacher (d. 1913), *Agadot ha-Tanna'im*, translated by Alexander Siskind Rabinovitz (d. 1945), Berlin and Jerusalem: Dvir, 1922 | 2,977 |
| IA | [motsaegolahzikhr00rabbuoft](https://archive.org/details/motsaegolahzikhr00rabbuoft) | Saul Pinchas Rabinowitz (d. 1910), *Motsa'e Golah*, Warsaw: Ahiasaf, 1894 | 2,836 |
| IA | [peereakhmemedina00gree](https://archive.org/details/peereakhmemedina00gree) | Jekuthiel Judah Greenwald (d. 1955), *Pe'ere Hakhme Medinatenu*, Sighet: A. Kaufman, 1910 | 2,776 |
| IA | [imanuelharomimon0000tche](https://archive.org/details/imanuelharomimon0000tche) | Shaul Tchernichovsky (d. 1943), *Immanuel ha-Romi*, Berlin: Eshkol, 1924 | 2,572 |
| IA | [mishnatrishonimt0000klat](https://archive.org/details/mishnatrishonimt0000klat) | Jacob Klatzkin (d. 1948), *Mishnat Rishonim*, Berlin: Eshkol, 1924 | 2,553 |
| IA | [igrothaasirmeiha00drey](https://archive.org/details/igrothaasirmeiha00drey) | Alfred Dreyfus (d. 1935), *Igrot ha-Asir me-I ha-Shedim*, translated by Abraham Shalom Friedberg (d. 1902), Warsaw: M. Spektor and E. Berman, 1898 | 2,487 |
| IA | [masaleeretsyirae00lewi](https://archive.org/details/masaleeretsyirae00lewi) | Elhanan Leib Lewinsky (d. 1910), *Massa le-Erets Yisra'el bi-Shnat 800*, Berlin: Kelal, 1922 | 1,917 |
| IA | [sepherhayyeyehud01mode](https://archive.org/details/sepherhayyeyehud01mode) | Leon of Modena (d. 1648), *Sefer Hayye Yehudah*, Kiev, 1912 | 1,491 |
| IA | [reginahashkenazi00ginsuoft](https://archive.org/details/reginahashkenazi00ginsuoft) | Pesach Ginzburg (d. 1947), *Regina Ashkenazi*, London: Iyim, 1918 | 1,304 |
| IA | [anshekayruan00pozn](https://archive.org/details/anshekayruan00pozn) | Samuel Abraham Poznański (d. 1921), *Anshe Kairuan*, Berlin, 1909 | 1,218 |
| IA | [maamarmagenetsin00mode](https://archive.org/details/maamarmagenetsin00mode) | Leon of Modena (d. 1648), *Ma'amar Magen ve-Tsinah*, edited by Abraham Geiger (d. 1874), Breslau: H. Sulzbach, 1856 | 1,145 |
| IA | [hegyoneshpinozah00rubi](https://archive.org/details/hegyoneshpinozah00rubi) | Salomon Rubin (d. 1910), *Hegyone Shpinozah*, Krakow: A. Faust, 1897 | 557 |

- **NLI scans:** From the collections of the National Library of Israel / מאוסף הספרייה הלאומית. Each record's IIIF manifest carries NLI's "public domain, free use" licence. They were fetched from NLI's IIIF service. No Google-digitized "public domain, non-commercial use" scan was used.
- **Internet Archive scans:** each item was scanned by a university library, named in the NOTICE (the University of Toronto for 15 of them; also Michigan, Columbia, Duke, Brandeis, Illinois, Ohio State and Florida). None was digitized by Google or comes from NLI. They were fetched from the Internet Archive, which publishes them without an explicit licence; the original conditions of each item on the Internet Archive still apply. Each item passed HeOCR's Internet Archive rights gate, and each book has its own recorded rights justification (author death years, publication year and place, digitizer, route), listed by id in the training record.
- **Text:** the Project Ben-Yehuda public-domain transcription of the same edition (public domain dump, release 2026-03), placed on each scanned line by HeOCR's alignment tool (hocrgen F8f). Lines were kept only where the alignment scored at least 0.9 and its text agreed with Tesseract's reading of the line at a similarity of at least 0.7. Tesseract only located the lines and chose between candidate spans at a line's edges; **no label is OCR output.**
- **Label normalisation:** Unicode NFC, logical order. Niqqud removed; `…` written as `...`, `„` as `"`, soft hyphens removed. The training labels contain no niqqud and no Latin letters; 2,820 of them contain digits.
- **Pointed prints dropped:** fully pointed books were left out (Hiawatha, Pines, Meyuhas, Mahamadim, Mandelkern, and two Internet Archive items). *Mi-Mitsrayim* and *Shirim* are unpointed prints whose edition text carries some niqqud; it was removed from their labels.
- **Two filters on the train lines:** 69 lines that share a word 6-gram with a selection line were removed (63 of them from *Shevet Sofer*, `atn3681`, which the Brainin selection book quotes), and so were 145 lines containing ׳, ״ or —, which are not in the character set.
- **Edition spelling:** Ben-Yehuda's text sometimes differs from the print. Such variants are in the labels.
- **All authors, translators and named contributors died more than 70 years ago,** so the books are in the public domain in Israel. Every book except *Shirim* (1938, one line) was printed before 1931 and is also past the US term; *Shirim* has no established US status.

**Selection lines (not trained on):** 7,113 lines of three NLI "public domain, free use" books, held out whole: Reuven Brainin (1862–1939), *Avraham Mapu: Hayav u-Sfarav*, Tushiya, 1928 ([990018546440205171](https://iiif.nli.org.il/IIIFv21/990018546440205171/manifest), 4,046 lines); Kadish Yehuda Silman (1880–1937), *Sansinim*, Tarbut, 1929 ([990020250940205171](https://iiif.nli.org.il/IIIFv21/990020250940205171/manifest), 3,046 lines); and Menahem Mendel Bodek (1825–1874), *Pe'er mi-Kedoshim*, Lemberg, about 1870 ([990010684570205171](https://iiif.nli.org.il/IIIFv21/990010684570205171/manifest), 21 lines). The first two are R6's selection books, so 99.7% of the selection lines are R6's.

### Training procedure and hyperparameters

The recipe is R6's. Only the line set and the number of iterations changed.

- **Start:** tessdata_best `heb` (`e12c65a`), its LSTM extracted with `combine_tessdata`. The network is the base's own, unchanged: `[1,36,0,1Ct3,3,16Mp3,3Lfys48Lfx96Lrx96Lfx192O1c1]`. R7 does not start from R6, so the R6–R7 comparison isolates the data and the training length.
- **Character set:** the base's, plus the maqaf `־` and the en dash `–`; R6's starter file, byte for byte. The output layer grew from 69 to 70 codes. The dictionary is the base's own word list, rebuilt with Tesseract's build files from [langdata_lstm](https://github.com/tesseract-ocr/langdata_lstm) `07930fd` (Apache-2.0).
- **Truth order:** each label is written in Tesseract's LSTM training order: the logical line reversed, punctuation not mirrored, digit runs kept left to right. Each line was converted to `.lstmf` with `tesseract … --psm 13 lstm.train`.
- **Trainer:** `lstmtraining --continue_from` the base, Tesseract 5.5.3, on CPU. Two arms of 200,000 iterations each (`--target_error_rate 0.01`), about two passes over the lines:
  - `lrdef`: the learning rate stored in the base, not set on the command line;
  - `lr1e4`: `--learning_rate 0.0001 --reset_learning_rate`.
- **Selection:** the checkpoint with the lowest BCER (`lstmeval`) on the selection lines, over all 89 saved checkpoints of both arms. That is `lr1e4` at iteration 117,100 (`heb_0.634_52608_117100`): BCER 1.567%, BWER 4.463%. The best `lrdef` checkpoint scored 2.095% / 5.733%.
- **Conversion:** `lstmtraining --stop_training` to `heb.traineddata`, renamed `heocr_r7.traineddata` for release (same bytes).
- **One training run.** It is not deterministic, and the bytes are not reproducible.

## Evaluation

### Real pages

- **Testing data:** E2d4c, 38 real printed Hebrew pages from 14 Hebrew Wikisource Indexes, with human-adjudicated references (hocrgen manifest `e2d4c_wikisource_printed_v7`), the same set and references as R6's card. They are a scored set under heocr-engine decision 0012: no training, tuning or checkpoint choice used them, R7 was scored on them once after selection, and their works are held out of training.
- **Metric:** CER and WER under hocrgen's `primary.v1` normalisation (hocrgen `d4a3414` `evaluate-references`), pooled over pages. Every engine reads whole pages with Tesseract 5.5.3, psm 3.
- **Intervals:** 95% paired bootstrap, resampling pages, then Wikisource Indexes (clusters); 2,000 resamples, seed 20261106.

| Engine | CER, 38 pages | WER, 38 pages | CER, 10 pages | WER, 10 pages |
|---|---|---|---|---|
| Stock Tesseract `heb` (Homebrew) | 0.226 | 0.473 | 0.384 | 0.588 |
| tessdata_best `heb` (R6's and R7's base) | 0.225 | 0.481 | 0.376 | 0.609 |
| R6 | 0.209 | 0.407 | 0.383 | 0.585 |
| **R7** | **0.209** | **0.393** | 0.393 | 0.568 |

| R7 minus | ΔCER, 38 pages (page; cluster) | ΔWER, 38 pages (page; cluster) |
|---|---|---|
| stock Tesseract | **−0.0168 [−0.0285, −0.0058]**; cl [−0.0336, +0.0063] | **−0.0798 [−0.1066, −0.0531]**; cl [−0.1203, −0.0238] |
| tessdata_best | −0.0157 [−0.0305, −0.0013]; cl [−0.0351, +0.0125] | −0.0877 [−0.1150, −0.0600]; cl [−0.1305, −0.0287] |
| R6 | −0.0005 [−0.0072, +0.0061]; cl [−0.0094, +0.0121] | −0.0135 [−0.0273, +0.0004]; cl [−0.0311, +0.0088] |

| R7 minus | ΔCER, 10 pages (page; cluster) | ΔWER, 10 pages (page; cluster) |
|---|---|---|
| stock Tesseract | +0.0091 [−0.0041, +0.0246]; cl [−0.0094, +0.0202] | −0.0201 [−0.0469, −0.0047]; cl [−0.0861, −0.0070] |
| tessdata_best | +0.0173 [−0.0037, +0.0362]; cl [−0.0096, +0.0392] | −0.0402 [−0.0872, −0.0141]; cl [−0.1588, −0.0191] |
| R6 | +0.0108 [−0.0011, +0.0186]; cl [−0.0097, +0.0210] | −0.0162 [−0.0463, +0.0000]; cl [−0.0648, −0.0066] |

- **Against stock Tesseract, on the 38 pages,** R7 lowers CER by 0.017 and WER by 0.080. It improves the CER of 24 pages, leaves 3 unchanged and worsens 11. The page interval on CER excludes zero; the cluster interval, over only 14 Indexes, does not.
- **Against R6: a tie.** The CER difference is 0.0005, far inside its interval. WER is 0.0135 lower; the page interval only just reaches zero (+0.0004), and the cluster interval includes it. R7 improves 22 pages against R6 and worsens 15. About seven times as many training lines did not move page-level CER.
- **No gain on the hardest pages.** The 10-page subset is the pages whose Wikisource Indexes fed none of HeOCR's glyph banks, and stock Tesseract's error is highest there. R7's CER there is 0.393, against stock's 0.384 and R6's 0.383. These differences are within their intervals, but the point estimate is worse than both. R7 improves 4 of the 10 pages against stock and worsens 6. Its WER on these pages is lower than stock's (the interval excludes zero) and R6's (the page interval reaches zero).
- **Why, not yet measured:** the line recognizer did improve (see [Selection lines](#selection-lines)). The likely reason the gain does not reach pages is that page-level error on this set is dominated by what the line model does not control: Tesseract's layout and reading order, and typefaces outside the training books.
- **Reference caveat:** E2d4c is the human audit of the earlier E2d3d references. Some audit proposals came from places where Tesseract and another engine agreed with each other but not with the reference, so the corrections may lean slightly toward what Tesseract reads. That is why every comparison above is paired on the same references.
- **No text overlap with training.** The 95,151 training labels share no word 6-gram with the 38 reference texts (letters only, niqqud stripped), whether each label is checked alone or the labels of each work are joined in reading order; the 7,113 selection labels share none either. The full Ben-Yehuda texts of the 30 training books share 10 6-grams with two reference pages, none of them in a training label:
  - 3 from two Bible verses (Isaiah 26:2, Psalms 118:20), quoted by one Frank story, as in R6's check;
  - 5 from one Bible verse (Psalms 102:14), quoted in Frankl's *Mi-Mitsrayim*;
  - 2 from a stock rabbinic title formula (אב"ד ור"מ בק"ק), in Greenwald's *Pe'ere Hakhme Medinatenu*.

  No evaluation manifest names an NLI record or an Internet Archive identifier of the training or selection books.

### Selection lines

On the 7,113 selection lines (Brainin, Silman and Bodek), scored with `lstmeval` (R6 and R7 against the shared starter, tessdata_best with its own character set):

| Model | BCER | BWER |
|---|---|---|
| tessdata_best `heb` (the base) | 11.516% | 23.304% |
| R6 (its selected checkpoint) | 2.056% | 5.406% |
| **R7** | **1.567%** | **4.463%** |

R7 lowers line BCER by about a quarter. The comparison favours R6: R6's checkpoint was chosen on Brainin and Silman, which are 99.7% of these lines, while R7's was chosen on all of them. The line set kept only lines whose text agreed with stock Tesseract's reading at 0.7 or more, so the figures are optimistic, and they compare models rather than give an absolute level. They are Tesseract-internal error rates on the training-order truth, not hocrgen `primary.v1`.

## Bias, risks and limitations

- **No gain over R6 on pages.** R7 ties R6 on CER, on the same base and recipe, with about seven times the lines. Its line-level gain did not carry through to whole pages.
- **A small gain over stock Tesseract,** by 0.017 CER, and no gain on the hardest pages, where its CER is slightly worse than stock's. It worsens 11 of 38 pages against stock.
- **Training data from 30 books,** printed in Warsaw, Vilna, Vienna, Berlin, Moscow, Jerusalem, London, New York and elsewhere between 1856 and 1938, all but three of them between 1881 and 1927. Smolenskin's collected works are 18.6% of the lines. Other typefaces, layouts and periods may gain less, or lose.
- **Printed Hebrew only.** Not for handwriting, Rashi script or non-Hebrew text.
- **No niqqud training.** The labels have no vowel points; pointed text was not evaluated.
- **Missing characters.** Geresh ׳, gershayim ״ and the em dash — are not in the character set, so R7 cannot output them; lines with them were left out of training.
- **Edition spelling.** Ben-Yehuda sometimes modernises or varies the spelling of the print, and the labels carry those variants.
- **Layout is Tesseract's.** R7 changes only the line recognizer. Page segmentation and reading order are Tesseract's own, and on complex layouts they dominate the error.
- **One training run, small evaluation.** The intervals cover page and Index sampling, not training seeds. 38 pages from 14 Indexes is a small scored set.

## Licence and attribution

- **Licence:** Apache-2.0. Copyright (c) 2026 HeOCR maintainers.
- **Base model:** a modified (fine-tuned) version of tessdata_best `heb`, Apache-2.0, from the Tesseract OCR project.
- **NOTICE:** redistributions must keep the NOTICE file. It credits:
  - the tessdata_best base model and the langdata_lstm build files (Apache-2.0);
  - the National Library of Israel for its scans, with every record id: From the collections of the National Library of Israel / מאוסף הספרייה הלאומית;
  - the Internet Archive and the contributing libraries for their scans, with every Internet Archive identifier; the original conditions of each item on the Internet Archive still apply;
  - Project Ben-Yehuda volunteers for the text;
  - Hebrew Wikisource, whose CC BY-SA transcriptions were used for scoring only, never for training.
- **No endorsement.** Neither the National Library of Israel, the Internet Archive, the contributing libraries, Project Ben-Yehuda, the Tesseract project nor Wikisource endorses HeOCR or this model.
- **The model contains no scan images or text files.** The line crops are not distributed with it.

## Provenance and reproduction

| Part | Identity |
|---|---|
| Base model | tessdata_best `heb.traineddata` at `e12c65a915945e4c28e237a9b52bc4a8f39a0cec`, git blob `0fc27335…`, sha256 `dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5` |
| Starter | R6's: base character set plus `־` and `–`, the base's word list, langdata_lstm `07930fd`; `heb.traineddata` sha256 `8b9d798a456bd1d4cd8bdf71b3d7b9d7579cea6cbd51302accd57f521669b846` |
| Line set | `bynli_lines_v2` (schema `s16c_benyehuda_nli_lines.v2`): `manifest.jsonl` sha256 `53dd7f1a10929ad4a60020ad7f42be62f27ee905cb7e6cfb0e319c5b2f5db7ca`, `summary.json` `faf3faf49dbe4e07fef01606ff2dd07ea1aca57062d666be564f57c061860a5f`; its 102,478 PNGs concatenated in sorted path order `39c1aa7da99866eea22130151e7c65f69cdff6f729f083dfd1400bff2e41e711`. Built with hocrgen `1921bbe`; hand-off record hocrgen `docs/f8f_r7_handoff.md` |
| Text | Project Ben-Yehuda `public_domain_dump`, release 2026-03 |
| Training | Tesseract 5.5.3 `lstmtraining` (Homebrew), 2026-11-11; selected checkpoint `lr1e4/heb_0.634_52608_117100` |
| Training record | `r7_training_run.json` (`heocr_tesseract_training_run.v1`), in this deposit |
| Scoring | hocrgen `d4a3414` `evaluate-references`, `primary.v1`, Tesseract 5.5.3 psm 3; references `e2d4c_wikisource_printed_v7` (manifest sha256 `0de65f63…`) |

The line set is not yet published. Its per-line manifest names each line's source record (NLI record id or Internet Archive identifier), canvas, box, Ben-Yehuda work and, for Internet Archive lines, the rights justification id, so the training set can be rebuilt from the public scans and texts, or rebuilt without any one book.

## Contact

Report problems and questions as issues on [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine/issues). A rights concern about any source book can be raised the same way, or by email to heocrproject@gmail.com; name the NLI record id or the Internet Archive identifier. The takedown procedure is at [heocr.github.io/rights.html](https://heocr.github.io/rights.html).

## Citation

Cite this model by its version DOI: [10.5281/zenodo.24126449](https://doi.org/10.5281/zenodo.24126449).
