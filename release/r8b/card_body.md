# HeOCR R8b: Hebrew printed-text recognition for Tesseract

**Publication status.** This model is unpublished. HeOCR will release models or an OCR pipeline after a registered real held-out comparison shows that it beats the state of the art on at least one document type.

R8b is a [Tesseract](https://github.com/tesseract-ocr/tesseract) language model (`.traineddata`) for printed Hebrew. HeOCR made it by continuing to train HeOCR R7 (former DOI `10.5281/zenodo.24126448`), itself a fine-tune of Tesseract's own `heb` model from [tessdata_best](https://github.com/tesseract-ocr/tessdata_best), for one pass over 196,275 lines:
- 158,104 real scanned lines from 45 public-domain books (8 National Library of Israel "public domain, free use" scans and 37 Internet Archive scans), labelled with the Project Ben-Yehuda transcription of the same edition;
- 19,533 lines rendered from 48 born-digital booklets of Israel's laws and regulations (Reshumot), labelled with the publisher's own text layer;
- 11 lines of one Hebrew Wikisource proofread page;
- 18,627 synthetic lines.

No label is OCR output.

Its character set adds geresh ׳, gershayim ״ and the em dash —, which R7 cannot output.

**Performance: not measured on a held-out set yet.** HeOCR reports accuracy only on held-out sets. No held-out score yet; HeOCR will score it once in a registered held-out run. That comparison will inform the publication decision.

- **Development comparison:** scanned Reshumot booklets were used for model selection.
- **How its checkpoint was chosen:** on selection lines from two books kept out of training (see [Training procedure](#training-procedure-and-hyperparameters)). Those books are read every round, so they are not held out, and their figures are not reported here.
- **Known cost: small, dark, grainy scans may lose.** On development lines it read Brainin's collected works, as scanned on the Internet Archive, worse than R7. That scan is small, dark and grainy, and little like R8b's training lines.

**R8b supersedes nothing. R7 remains valid.** Use R8b for modern printed Hebrew, and for text with ׳ ״ —, which R7 cannot output. R7's card, record and deposit are unchanged.

This is a standalone Tesseract model.

| | |
|---|---|
| File | `heocr_r8b.traineddata` (trained as `heb.traineddata`), 3,633,477 bytes |
| sha256 | `8cb22dbeb195c3c0ffbe9c66cf956d8c2052d3b1c4a872234a85c975c4526117` |
| Model type | recognition (line-level LSTM, CTC); Tesseract does the page layout |
| Format | Tesseract 4/5 LSTM `traineddata`, LSTM only (`--oem 1`; no legacy engine). Trained and tested with Tesseract 5.5.3 |
| Continued from | HeOCR R7 (`10.5281/zenodo.24126448`), the checkpoint R7 was packed from |
| Base model | tessdata_best `heb.traineddata` at [`e12c65a`](https://github.com/tesseract-ocr/tessdata_best/tree/e12c65a915945e4c28e237a9b52bc4a8f39a0cec) (Apache-2.0), sha256 `dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5`, fine-tuned (modified) by HeOCR as R7 and then R8b |
| Licence | Apache-2.0, Copyright (c) 2026 HeOCR maintainers (see LICENSE and NOTICE) |
| Training record | `r8b_training_run.json` (`heocr_tesseract_training_run.v1`) |
| Code | [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine) |

## Uses

- **OCR of printed Hebrew pages** in the square script without niqqud: modern print such as government gazettes, and 19th- and early-20th-century book type. Use it in place of Tesseract's `heb`.
- **Line recognition** of single printed Hebrew line images, for example lines found by another segmenter.
- **A research baseline** for Hebrew OCR on real scans, and for comparison with R7.

### Out of scope

- **Handwriting.** R8b was trained on print only.
- **Niqqud (vowel points) and cantillation.** The training labels have none. How R8b behaves on pointed text was not measured.
- **Rashi script and other non-square Hebrew scripts.** R8b's recipe left out the rabbinic line set that was tested in a second arm.
- **Unsupervised transcription.** Check the output.
- **Documents that are not mainly Hebrew.** Latin letters are not in its character set; Reshumot lines containing them were left out.

## Local use with an authorized copy

Install Tesseract 4 or 5 (tested with 5.5.3). Put `heocr_r8b.traineddata` in a directory, say `DIR`, and pass that directory and the language name `heocr_r8b`.

**Whole pages: page segmentation mode 3** (automatic layout, Tesseract's default).

```sh
tesseract page.png out -l heocr_r8b --tessdata-dir DIR --psm 3
```

This writes `out.txt`, in logical (reading) order. Whole-page accuracy was not measured for R8b.

**Single line images: psm 13** (raw line). HeOCR reads and scores line images this way. Do not use psm 7 on line crops: with stock `heb` and with R6, psm 7 returned empty text on crops that carry a sliver of the neighbouring line.

```sh
tesseract line.png out -l heocr_r8b --tessdata-dir DIR --psm 13
```

Notes:
- **`--tessdata-dir` replaces Tesseract's data directory.** Output formats other than plain text (`tsv`, `hocr`, `pdf`, `alto`) read their config files from `DIR/configs`. Link or copy the `configs` folder of your Tesseract installation into `DIR`, or put `heocr_r8b.traineddata` in your installation's own tessdata directory and drop `--tessdata-dir`.
- **The language name is the file name without `.traineddata`.** `heocr_r8b` follows tessdata's naming. It combines with other models in the usual way, for example `-l heocr_r8b+eng`, which runs but was not evaluated.
- **Maqaf and quotation marks.** R8b writes the maqaf `־` (U+05BE) where many texts write `-`, and it writes `׳ ״` where many texts write `' "`. Fold them if your downstream text uses the ASCII forms.

## Training details

### Training data

**Lines:** 196,275 in one seeded-shuffle list (seed 20261111). Every label character is in the character set.

| Source | Line set | Lines | Rights |
|---|---|---|---|
| R7's 30 books: 7 NLI and 23 Internet Archive university-library scans | `bynli_lines_v2` | 95,296 | NLI "public domain, free use"; Internet Archive, original conditions apply |
| 15 more books: 1 NLI scan and 14 Internet Archive scans (4 of them digitized by Google) | `bynli_lines_v3` | 62,808 | as above |
| 48 Reshumot booklets, *Sefer ha-Hukim* (12,602) and *Kovetz ha-Takanot* (6,931), 2006–2026, rendered from born-digital PDFs | `reshumotlines_v1` | 19,533 | PD-IL (Copyright Act 2007 §6) |
| One Wikisource proofread page: Buber, *Sifrei de-Agadeta*, Vilna 1886, p. 136 | `wslines_v1` | 11 | text CC BY-SA 4.0 (Hebrew Wikisource contributors) |
| Synthetic lines from HeOCR's S17a generator | `s17a_addon_v1.1` | 18,627 | CC0 |

- **R7's lines** are the 95,151 R7 trained on, plus 145 lines with ׳, ״ or — that R7's character set could not hold. Their authors, titles and editions are in R7's card and in the NOTICE. By record, with R8b's line counts:
  - NLI: [990017640460205171](https://iiif.nli.org.il/IIIFv21/990017640460205171/manifest) (6,100), [990020308000205171](https://iiif.nli.org.il/IIIFv21/990020308000205171/manifest) (6,076), [990020495520205171](https://iiif.nli.org.il/IIIFv21/990020495520205171/manifest) (6,052), [990020522850205171](https://iiif.nli.org.il/IIIFv21/990020522850205171/manifest) (1,511), [990020466440205171](https://iiif.nli.org.il/IIIFv21/990020466440205171/manifest) (72), [990019385920205171](https://iiif.nli.org.il/IIIFv21/990019385920205171/manifest) (8), [990013538860205171](https://iiif.nli.org.il/IIIFv21/990013538860205171/manifest) (1);
  - Internet Archive (university-library scans): [kolsifreperetsbe03smoluoft](https://archive.org/details/kolsifreperetsbe03smoluoft) (6,100), [sifrehazikhronot00mont](https://archive.org/details/sifrehazikhronot00mont) (6,100), [kolsifreperetsbe01smoluoft](https://archive.org/details/kolsifreperetsbe01smoluoft) (6,096), [kolsifreperetsbe05smoluoft](https://archive.org/details/kolsifreperetsbe05smoluoft) (5,489), [miyarketetevel008800](https://archive.org/details/miyarketetevel008800) (4,760), [ldpd_15772050_000](https://archive.org/details/ldpd_15772050_000) (4,639), [mabeothayehudims00raff](https://archive.org/details/mabeothayehudims00raff) (4,137), [atn3681.0001.001.umich.edu](https://archive.org/details/atn3681.0001.001.umich.edu) (4,065), [maloketravseadya00bornuoft](https://archive.org/details/maloketravseadya00bornuoft) (3,658), [mimitsrayimhusef00fran](https://archive.org/details/mimitsrayimhusef00fran) (3,590), [ademataidibruivr00benyuoft](https://archive.org/details/ademataidibruivr00benyuoft) (2,980), [agadothatanaim11bach](https://archive.org/details/agadothatanaim11bach) (2,977), [motsaegolahzikhr00rabbuoft](https://archive.org/details/motsaegolahzikhr00rabbuoft) (2,852), [peereakhmemedina00gree](https://archive.org/details/peereakhmemedina00gree) (2,777), [imanuelharomimon0000tche](https://archive.org/details/imanuelharomimon0000tche) (2,572), [mishnatrishonimt0000klat](https://archive.org/details/mishnatrishonimt0000klat) (2,553), [igrothaasirmeiha00drey](https://archive.org/details/igrothaasirmeiha00drey) (2,498), [masaleeretsyirae00lewi](https://archive.org/details/masaleeretsyirae00lewi) (1,917), [sepherhayyeyehud01mode](https://archive.org/details/sepherhayyeyehud01mode) (1,491), [reginahashkenazi00ginsuoft](https://archive.org/details/reginahashkenazi00ginsuoft) (1,305), [anshekayruan00pozn](https://archive.org/details/anshekayruan00pozn) (1,218), [maamarmagenetsin00mode](https://archive.org/details/maamarmagenetsin00mode) (1,145), [hegyoneshpinozah00rubi](https://archive.org/details/hegyoneshpinozah00rubi) (557).
- **The 15 new books** (`bynli_lines_v3`):

  | Source | Record | Book | Lines |
  |---|---|---|---|
  | IA | [zikhronotlebetda01reck](https://archive.org/details/zikhronotlebetda01reck) | Abraham Shalom Friedberg (d. 1902), *Zikhronot le-Vet David*, Warsaw, 1893 | 6,100 |
  | IA | [sifruthahisoriya11kaha](https://archive.org/details/sifruthahisoriya11kaha) | Abraham Kahana (d. 1946), *Sifrut ha-Historiyah ha-Yisre'elit*, Warsaw, 1922 | 6,094 |
  | IA | [yotsrehasifrutha00zitr](https://archive.org/details/yotsrehasifrutha00zitr) | Shmuel Leib Citron (d. 1930), *Yotsre ha-Sifrut ha-Ivrit ha-Hadashah*, Vilna, 1922 | 6,039 |
  | IA (Google) | [afahleneemaniml00fngoog](https://archive.org/details/afahleneemaniml00fngoog) | Samuel Joseph Fuenn (d. 1891), *Safah le-Ne'emanim*, Vilna, 1881 | 5,750 |
  | IA | [kolkitveylkatsen018800](https://archive.org/details/kolkitveylkatsen018800) | Judah Leib Katzenelson (d. 1917), *Kol Kitve Y. L. Katsenelson*, St Petersburg, 1905 | 5,716 |
  | IA | [seferhademaotmeo0000bern](https://archive.org/details/seferhademaotmeo0000bern) | Simon Bernfeld (d. 1940), *Sefer ha-Dema'ot*, Berlin, 1923 | 5,350 |
  | IA | [divreyemeolam02schuuoft](https://archive.org/details/divreyemeolam02schuuoft) | Kalman Schulman (d. 1899), *Divre Yeme Olam*, Vilna, 1868 | 4,668 |
  | IA | [bioretletoldotha01gott](https://archive.org/details/bioretletoldotha01gott) | Abraham Baer Gottlober (d. 1899), *Bikoret le-Toldot ha-Kara'im*, Vilna, 1865 | 4,662 |
  | IA | [zikhronotlevetda01frie](https://archive.org/details/zikhronotlevetda01frie) | Abraham Shalom Friedberg (d. 1902), *Zikhronot le-Vet David*, Warsaw, 1904 | 4,150 |
  | IA | [tserorperaimvehu00kovn](https://archive.org/details/tserorperaimvehu00kovn) | Abraham Uri Kovner (d. 1909), *Tseror Perahim*, Odessa, 1868 | 3,616 |
  | IA (Google) | [mikhtavimmiarsh00mezagoog](https://archive.org/details/mikhtavimmiarsh00mezagoog) | Yehoshua Mezah (d. 1917), *Mikhtavim mi-Sar shel Yam*, Warsaw, 1886 | 3,452 |
  | IA (Google) | [korothayehudimb00friegoog](https://archive.org/details/korothayehudimb00friegoog) | Abraham Shalom Friedberg (d. 1902), *Korot ha-Yehudim bi-Sefarad*, Warsaw, 1893 | 2,968 |
  | NLI | [990026910840205171](https://iiif.nli.org.il/IIIFv21/990026910840205171/manifest) | Yaakov Bachrach (1824–1896), *Sefer ha-Massa le-Erets ha-Kedoshah*, Warsaw, 1884 | 2,319 |
  | IA | [sipurim00nombuoft](https://archive.org/details/sipurim00nombuoft) | Hirsh David Nomberg (d. 1927), *Sipurim*, Warsaw, 1905 | 1,291 |
  | IA (Google) | [tsitsimuferaimm00geiggoog](https://archive.org/details/tsitsimuferaimm00geiggoog) | Abraham Geiger (d. 1874), *Tsitsim u-Ferahim*, Leipzig, 1856 | 633 |

- **NLI scans:** From the collections of the National Library of Israel / מאוסף הספרייה הלאומית. Each record's IIIF manifest carries NLI's "public domain, free use" licence. They were fetched from NLI's IIIF service. No Google-digitized "public domain, non-commercial use" scan was used.
- **Internet Archive scans:** 33 were scanned by university libraries, named in the NOTICE. Four were digitized by Google, and each is credited as "Digitized by Google; retrieved via the Internet Archive" with its contributing library: `afahleneemaniml00fngoog`, `korothayehudimb00friegoog` and `tsitsimuferaimm00geiggoog` (University of California), and `mikhtavimmiarsh00mezagoog` (unknown library). They are admitted under rule 3 of HeOCR's legal strategy (hocrgen `planning/decisions/2026-11-10-legal-strategy.md`) and heocr-engine decision 0015, because they were fetched from the Internet Archive, not from Google or NLI. Per the strategy's hygiene rule, canvas 0 (Google's usage-guidelines page) was excluded from each of them, no "Digitized by Google" watermark was found on any other page, and no training line comes from canvas 0. None of the Internet Archive scans comes from NLI. The Internet Archive publishes them without an explicit licence; the original conditions of each item on the Internet Archive still apply. Each item passed HeOCR's Internet Archive rights gate, and each Ben-Yehuda work aligned to it has its own recorded rights justification, listed by id in the training record.
- **Reshumot lines:** rendered by HeOCR (150 dpi grey) from born-digital PDFs of the official gazette, labelled with the publisher's own text layer of each line, which was checked against the render. Laws and regulations have no copyright in Israel (Copyright Act 2007 §6). Their status outside Israel is not asserted. Every booklet passed a born-digital check and HeOCR's evaluation-reserve guard: none is an evaluation booklet.
- **Wikisource lines:** the proofread transcription is CC BY-SA 4.0 ([permalink](https://he.wikisource.org/w/index.php?oldid=763704)); the scan is a Wikimedia Commons file of a University of Toronto scan. Under heocr-engine decision 0016 the weights stay Apache-2.0 with this credit, and no word list was built from the text (see [Word list](#word-list)).
- **Synthetic lines:** made by HeOCR's S17a generator, which HeOCR trained from scratch on its own line pairs. Its inputs are renders in Frank Ruhl Libre (SIL OFL 1.1), style crops from 29 of R7's books, and Project Ben-Yehuda text. The generator and the build recipe are in [HeOCR/hocrsyngen](https://github.com/HeOCR/hocrsyngen) at `3b55d4aff3de9f3211bc1573f2e0644748e84d63`, under `experiments/learned_generation_v0/s17a_scanifier/`.
- **Filters:** lines with characters outside the character set were dropped (107 Reshumot lines, Latin mostly), and so were training lines sharing a word 6-gram with evaluation text: 74 from the new books, 347 Reshumot lines, and 4,752 more found by HeOCR's evaluation check (3,801 Wikisource lines from Indexes with verified line references, and 951 Reshumot lines matching evaluation booklets, mostly date headers and enactment formulas).
- **All authors, translators and named contributors of the books died more than 70 years ago,** so the books are in the public domain in Israel. Every book except *Shirim* (1938, one line) was printed before 1931 and is also past the US term.

**Selection lines (not trained on):** 3,000 lines, 1,500 seeded from each of two Internet Archive university-library scans, kept out of training whole (they are read every round, so they are not a held-out set): Mordechai ben Hillel Hacohen (d. 1936), *Kevar: Pirke Zikhronot*, Warsaw, 1922 ([kevarpirezikhron00haco](https://archive.org/details/kevarpirezikhron00haco)); and Aaron Bernstein (d. 1884), *Yedi'ot ha-Teva*, translated by David Frischmann (d. 1922), Warsaw, 1883 ([yediothateva06bernuoft](https://archive.org/details/yediothateva06bernuoft)).

### Training procedure and hyperparameters

- **Start:** R7's selected checkpoint (`lr1e4/heb_0.634_52608_117100`, the one R7 was packed from), with R7's starter as the old traineddata. The network is the base's own, unchanged: `[1,36,0,1Ct3,3,16Mp3,3Lfys48Lfx96Lrx96Lfx192O1c1]`.
- **Character set:** the R8 starter (sha256 `202272593630b4eddba57d5b09f5d3a142ed551b9550094e2885eb1b359fe037`, 73 codes): R7's starter plus geresh `׳`, gershayim `״` and the em dash `—`. The output layer grew from R7's 70 codes to 73.
- **Truth order:** each label is written in Tesseract's LSTM training order: the logical line reversed, punctuation not mirrored, digit runs kept left to right. Each line was converted to `.lstmf` with `tesseract … --psm 13 lstm.train`.
- **Trainer:** `lstmtraining --continue_from` R7, Tesseract 5.5.3, on CPU, `--learning_rate 0.0001 --reset_learning_rate`, for one epoch (196,275 iterations). The run exited cleanly. No `--eval_listfile`: lstmtraining's background tester crashed the first launches, so selection ran afterwards.
- **Arms:** a second arm added 17,496 rabbinic old-printed lines. It was compared with this one on the selection books and on rendered Reshumot development lines, and not chosen. It was dropped from the recipe and is not released.
- **Selection:** the checkpoint with the lowest line CER on the 3,000 selection lines under the `line_fold_v1` profile (below), over 28 saved checkpoints and snapshots. The winner is the final snapshot. The selection books chose the checkpoint, so the choice says nothing about performance. An earlier pick by Tesseract's own BCER was withdrawn after HeOCR's evaluation found two measurement problems (lstmeval drops lines a model cannot encode, and the references write maqaf inconsistently).
- **Conversion:** `lstmtraining --stop_training` to `heb.traineddata`, renamed `heocr_r8b.traineddata` for release (same bytes).
- **One training run.** It is not deterministic, and the bytes are not reproducible.

### Word list

The dictionary is the tessdata_best base's own word list, and no entry comes from any training text. This was checked by decoding each model's `lstm-word-dawg` with `dawg2wordlist` and its own unicharset, then comparing the sorted entries:
- **R8b has the same 70,171 entries as R7.**
- **They are tessdata_best's 70,171 entries in right-to-left order.** Reversed, the two lists agree except for 24 bracket or arrow tokens, whose `( )` and `< >` are mirrored.
- **The dawg bytes differ, as expected.** A dawg rebuilt for a larger character set cannot match the original's bytes. The `lstm-word-dawg` sha256 values are tessdata_best `f34e9fa5165077f285ccff7c0f53a8e96b74ef37c92038e472770cfc83433171`, R7 `cddcc086c241eeaf0f29b77f7955770d4fe3b2832f8fec986e53c7a0a579fcdb` and R8b `a618186eb88789a203c2475ec30fbe2277427f97d063a8bf91cc564c0a166649`.

So decision 0016 holds: no word list was built from Wikisource text.

## Evaluation

The R7-derived readers shown here inherit R7 checkpoint-selection exposure to 7,092 development rows from two sources now reserved in line_verify. Comparisons on those sources are selection-exposed.

**Performance: not measured on a held-out set yet.** HeOCR reports a model's accuracy only on sets held out from its training, selection and tuning. R8b has no such score yet. No held-out score yet; HeOCR will score it once in a registered held-out run.

- **What was used to choose it is not reported as performance:**
  - the release decision: a silver development set of 3,254 lines from 55 scanned Reshumot dev booklets of 1953–2003 (`olbreshumotlines_v1_dev`), labelled with the same-wording text of the Open Law Book on Hebrew Wikisource (ספר החוקים הפתוח, CC BY-SA 4.0), where it was compared with R7, the unreleased arm and stock Tesseract;
  - the checkpoint: the two selection books, *Kevar* and *Yedi'ot ha-Teva*, which are kept out of training but read every round;
  - the development report sets that guard against regressions: Silman, Brainin (the NLI scan and the Internet Archive scan), rendered Reshumot dev, Mekhilta de-Rabbi Shimon, Wikisource dev and Bodek.
- **Where those figures are:** in HeOCR evaluation's dev record, `eval-domains/outputs/r8b_release_figures_v1.json` (sha256 `22c0305ddafe6f436599df115c1c71345fed3685feae2c3cd9198b5e989909d9`). They are dev and selection figures, not performance.
- **Scope:** small, dark and grainy scans are a distinct input condition. Include them in a future registered evaluation.
- **Next:** a registered held-out run, against R7 and stock tessdata_best `heb` (the base), read the same way. That comparison will inform the publication decision.
- **Scoring profile** for that run: `line_fold_v1` (sha256 `2e2627104be4f27dc3204787dd3ff4f8591d95d1d96294c65833d2773041d317`): NFC, whitespace collapsed, and five folds of signs the references write inconsistently: `־`→`-`, `׳`→`'`, `״`→`"`, `“ ” „`→`"`, `—`→`–`. Nothing else is folded. Every reference line is scored, at psm 13, and characters a model cannot output are charged.

### Text overlap with training

**Audit scope.** The figures below describe a historical six-word overlap screen against the reference revisions available at the time. Short matches, source and edition identity, and inherited checkpoint-selection exposure require separate checks. A registered comparison will apply [contamination policy v2](../../planning/decisions/0028-contamination-policy-v2.md) to the exact reader lineages and frozen reference set. It will report the full eligible set and the common verified non-overlap subset, with denominators and any gaps in training ancestry. For the closed use cases, [decision 0024](../../planning/decisions/0024-use-case-benchmarks-modern-print.md) limits public reporting to anonymized aggregates.

The training labels were checked against the evaluation text with word 6-grams (letters only, niqqud stripped).
- **HeOCR's evaluation check** finds no training line sharing a 6-gram with the P-mod evaluation booklets, wave 1, the verified line references or the restricted tender pages.
  - 158 training lines share one with the dev and report sets: 62 with Brainin IA, 56 with Mekhilta and 40 with Reshumot dev; none with *Kevar* or *Yedi'ot ha-Teva*.
  - 13 share one with the OLB dev set, all Reshumot boilerplate.
- **Mid-century test pages** (heocr-eval's human-reviewed set, not yet scored), rechecked 2026-11-13 with their full text: the batch v1 pre-fills, the blind pre-fills and Claude's readings.
  - 116 training lines share a 6-gram with that text, and 33 of the 298 pages hold a training 6-gram, each on fewer than 3 in 10 of its lines.
  - An earlier check used an incomplete version of this text and found 81 lines.
  - When R8b gets a mid-century score, the headline will cover only pages with no exposure to R8b's or R7's training lines. The full set will be reported second, with its exposure stated.
- **Why the overlap reached training** (found 2026-11-13). R8b's list builder checked only its newly added sources against the dev and report text. The lines it carried over from R8a, and the S17a add-on, were checked only against the two new dev units. Its letters-only 6-grams also let through some Reshumot lines that share word 6-grams with Reshumot dev. The OLB dev set was built after training.
  - **Whole-list coverage from R9 on.** Check the final training list, including inherited inputs, against the registered targets. Under policy v2, source exclusions and permitted different-format text exposure have separate dispositions.
- **The 38 E2d4c reference pages:** 1 of the 196,275 training labels shares a 6-gram, the abbreviated rabbinic title formula אב"ד ור"מ דק"ק. The method splits it into six tokens; it is boilerplate, not shared text. R8b has no score on those pages.

## Bias, risks and limitations

- **Not measured on a held-out set yet.** See [Evaluation](#evaluation). R8b has no whole-page score.
- **A regression on one scan.** On development lines R8b read Brainin's Internet Archive scan worse than R7. Small, dark, grainy scans may lose in the same way.
- **Training data** from 45 books printed between 1856 and 1938, most of them between 1865 and 1925, and from modern Reshumot booklets (2006–2026). Smolenskin's collected works are 9.0% of the lines, and the largest Reshumot booklet 1.8%. Other typefaces, layouts and periods may gain less, or lose.
- **Printed Hebrew only.** Not for handwriting, Rashi script or non-Hebrew text, and no Latin letters.
- **No niqqud training.** The labels have no vowel points; pointed text was not evaluated.
- **Sign conventions.** R8b writes `־` and `׳ ״`, where many texts and references write `-` and `' "`. Raw CER against such references overstates its error; HeOCR's scoring folds them.
- **Edition spelling.** Ben-Yehuda sometimes modernises or varies the spelling of the print, and the labels carry those variants.
- **Layout is Tesseract's.** R8b changes only the line recognizer.
- **One training run.** Training-seed variation is not measured.

## Licence and attribution

- **Licence:** Apache-2.0. Copyright (c) 2026 HeOCR maintainers.
- **Base model:** a modified (fine-tuned) version of tessdata_best `heb`, Apache-2.0, from the Tesseract OCR project, through HeOCR R7.
- **NOTICE:** redistributions must keep the NOTICE file. It credits:
  - the tessdata_best base model and the langdata_lstm build files (Apache-2.0);
  - the National Library of Israel for its scans, with every record id: From the collections of the National Library of Israel / מאוסף הספרייה הלאומית;
  - the Internet Archive and the contributing libraries for their scans, with every Internet Archive identifier; the original conditions of each item on the Internet Archive still apply;
  - the four scans digitized by Google; retrieved via the Internet Archive, with their contributing library, their hygiene and the decisions that admit them;
  - Reshumot, the official gazette of the State of Israel, for the laws and regulations;
  - Hebrew Wikisource contributors for the 11 training lines' text (CC BY-SA 4.0), and for scoring references;
  - Project Ben-Yehuda volunteers for the text;
  - the Frank Ruhl Libre typeface (SIL OFL 1.1) behind the synthetic lines.
- **No endorsement.** Neither the National Library of Israel, the Internet Archive, Google, the contributing libraries, Reshumot or the State of Israel, Project Ben-Yehuda, the Tesseract project, Wikimedia Commons nor Wikisource endorses HeOCR or this model.
- **The model contains no scan images or text files.** The line crops are not distributed with it.

## Provenance and reproduction

| Part | Identity |
|---|---|
| Base model | tessdata_best `heb.traineddata` at `e12c65a915945e4c28e237a9b52bc4a8f39a0cec`, sha256 `dbaa827aea6bc21215638447f17783a1004987c2d0bf5573d111fee397abdae5` |
| Continued from | HeOCR R7, checkpoint `lr1e4/heb_0.634_52608_117100` (sha256 `7bfac6d3…`), released as `heocr_r7.traineddata` (sha256 `95faab81…`) |
| Starter | the R8 starter: R7's character set plus `׳ ״ —` (73 codes), the base's word list, langdata_lstm `07930fd`; `heb.traineddata` sha256 `202272593630b4eddba57d5b09f5d3a142ed551b9550094e2885eb1b359fe037` |
| Line sets | `bynli_lines_v2` (manifest sha256 `53dd7f1a…`), `bynli_lines_v3` (`4cba250f…`), `reshumotlines_v1` (`a6de99ba…`), `wslines_v1` (`25ed7ff9…`), `s17a_addon_v1.1` (`3f79461b…`); full values in the training record |
| Text | Project Ben-Yehuda `public_domain_dump`, release 2026-03 |
| Synthetic lines | `s17a_addon_v1.1`: generator and build recipe in HeOCR/hocrsyngen `3b55d4aff3de9f3211bc1573f2e0644748e84d63`, `experiments/learned_generation_v0/s17a_scanifier/`; generator weights sha256 `efdb5f82…` |
| Training | Tesseract 5.5.3 `lstmtraining` (Homebrew), 2026-11-12; selected checkpoint `main/heb_snap_final` (sha256 `5526f713…`) |
| Training record | `r8b_training_run.json` (`heocr_tesseract_training_run.v1`), in this directory |
| Scoring | `eval-domains/scripts/score_lines.py`, profile `line_fold_v1`; dev and selection figures behind the choice in `r8b_release_figures_v1.json` (sha256 `22c0305d…`), not performance |

The line sets are not yet published. Their per-line manifests name each line's source (NLI record id, Internet Archive identifier, Reshumot booklet or Wikisource page), its box and its label source, and for Internet Archive and Wikisource lines the rights justification id, so the training set can be rebuilt from the public sources, or rebuilt without any one of them.

## Contact

Report problems and questions as issues on [HeOCR/heocr-engine](https://github.com/HeOCR/heocr-engine/issues). A rights concern about any source can be raised the same way, or by email to heocrproject@gmail.com; name the NLI record id, the Internet Archive identifier, the Reshumot booklet or the Wikisource page. The takedown procedure is at [heocr.github.io/rights.html](https://heocr.github.io/rights.html).

## Archive reference

Former Zenodo version DOI: `10.5281/zenodo.24372346`.
