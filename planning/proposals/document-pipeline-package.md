# Proposal: `heocr`, a Python package that gets Hebrew text out of any document

- Status: **proposal**, for the maintainer's decision. The maintainer decided §9 item 5 and the first half of item 4 on 2026-11-16; nothing else here is decided. The other decisions it needs are in §9.
- Date: 2026-11-16
- Written by: `lead[claude/claude-code#shay-macbook-m4]@heocr/opensource`, at the maintainer's request.
- Serves: [decision 0019](../decisions/0019-top-goal-document-pipeline.md), the top goal.
- Builds on: decision 0002 (engines emit raw text), decision 0014 (open release; no licence-tainted inputs), and decisions 0017 and 0018 (evaluation per document set).

## 1. What we learned before writing this

Two pipelines were built for Israeli government tender documents and compared on the same 132 files: 71 PDF, 57 DOCX, 3 DOC and 1 HTML. One was a volunteer's evaluation project; the other was a production transcription pipeline. The maintainer has released the volunteer's code for reuse (§9, item 4). The findings that shape this proposal:

1. **Kind of content predicts the best tool; file origin does not.**
   - 59 of the 71 PDFs were made in Word, yet the tools differed sharply within that group.
   - What decides is the kind of content on the page:

| Content | Best tool in the comparison | What the others did |
|---|---|---|
| Running text in a PDF with a text layer | docling | Text-layer readers split words: 6.4 per 1,000 against 0.1 |
| Tables | Word's PDF conversion, or pymupdf4llm | docling reversed the word order in 84% of table cells |
| Image-only pages | The production pipeline's OCR: 87% of words found in a dictionary | The other tools returned gibberish or nothing |

2. **DOCX automatic numbering is not in the text.**
   - Reading the XML gave 0.6% correct multi-level section numbers.
   - Letting Word render the numbers first (over COM, on Windows) gave 99%.
   - The numbers can be computed from `numbering.xml` without Word. That is the clearest case for HeOCR's own code.
3. **A PDF text layer comes in several states, and each needs different handling.** Real examples from the corpus:
   - **Visual order:** markitdown reverses every Hebrew word.
   - **Broken font mappings:** U+F8FF in place of every נ; private-use codes for final letters in the David font; ð in place of נ, from a cp1255/Latin-1 mix-up.
   - **A garbage text layer:** OCR from an engine without Hebrew left text such as `CMLL LLIL`, and tools logged the page as "ok".
   - **Reversed numbers after conversion:** `000,005,8` for 8,500,000 ₪.
   - **Numbers drawn as images** inside text pages.
   - **Layout and decoration:** two-page spreads, white "ריק" placeholder text for screen readers, and repeated site menus.
4. **Silent loss is the worst failure.**
   - An OCR route dropped a table row and marked the page as fine.
   - Word's conversion reversed amounts that looked plausible.
   - Errors that are systematic and detectable can be repaired in code. Silent ones cannot.
5. **Licences rule out the common shortcuts.**
   - PyMuPDF (and so pymupdf4llm) is AGPL-3.0 or commercial.
   - Surya's weights are non-commercial (older versions) or limited by funding and revenue (2.5).
   - Neither fits decision 0014.

## 2. What the package is

**One call, any document.**

```python
import heocr
doc = heocr.extract("tender.pdf")      # or .docx, .doc, .png, ...
doc.text        # plain text in reading order
doc.markdown    # headings, numbered sections and tables kept
doc.to_json()   # heocr_document.v1: every block with its route, tool, repairs and flags
```

```sh
heocr tender.pdf -o tender.md
```

- **Name and repository:** the package is `heocr`; the name is free on PyPI as of 2026-11-16. It lives in a new repository, `HeOCR/heocr`, under Apache-2.0.
- **What heocr-engine stays:** the research runtime for training and evaluating models. The package uses the models it releases.
- **Requirements:** Python 3.11 or later, on Linux, macOS and Windows.
- **Offline:** the core makes no network calls. Optional model downloads are explicit and pinned by sha256.

## 3. Routing

The package decides in four layers. Every decision is recorded in the output.

### 3.1 File type
- Magic bytes and container parts decide the format, never the file extension.
- Formats: PDF, DOCX, DOC, XLSX, PPTX, ODT, RTF, HTML, images, and ZIP (recursive, with limits).

### 3.2 Formats that carry text
- **DOCX, PPTX and XLSX:**
  - HeOCR code reads the OOXML with defusedxml.
  - It renders automatic numbering from `numbering.xml`: levels, formats, restarts, overrides, and Hebrew counting (א, ב, …).
  - It takes headings from outline levels as well as style names.
  - It drops hidden text, keeps line breaks inside table cells, and keeps tables right to left.
  - Headers, footers, footnotes and comments come out separately, never mixed into the body.
- **DOC, RTF and ODT:** converted to DOCX by an optional external LibreOffice, then handled as DOCX.
- **Images embedded in office files** take the OCR route (§3.4). Their text is attached at the image's place in the text.

### 3.3 PDF: each page is placed in a text-layer class

Each page is measured, then placed in one class. Signals:

- **Amount of text:** characters in the text layer.
- **Images and drawings:** share of the page covered by images; number of vector paths.
- **Script:** share of Hebrew letters among all letters.
- **Visual order:** how often a word starts with a final letter (ךםןףץ).
- **Hebrew quality:** dictionary hit rate of the Hebrew words.
- **Broken characters:** counts of U+FFFD, private-use codes, and Latin-1 letters next to Hebrew letters.
- **Fonts:** font names and their ToUnicode maps.

| Class | What it is | Route |
|---|---|---|
| **T1** | Correct text layer in logical order | Text from the layer. HeOCR code builds right-to-left lines from character boxes. |
| **T2** | Text layer in visual order | Same text, reordered with HeOCR's bidi code |
| **T3** | Broken font mapping that can be recovered | Repairs (§3.5), driven by font and character evidence, not file names |
| **T4** | Garbage text layer (a foreign OCR, or mapping that can't be recovered) | Ignore the layer; OCR route |
| **T5** | Image only | OCR route |
| **T6** | Text layer plus text that exists only as image or vector drawing | Text layer, plus region OCR for the uncovered regions |

- **Spreads:** a page exactly twice the width of a standard page is split into two pages, right half first. An unknown wide size is reported, not guessed.
- **Columns:** when the column order is ambiguous, the page is flagged rather than guessed.
- **Tables:**
  - Cells are found from ruling lines and word geometry.
  - Each cell takes its words from the text layer by position, so no word is invented.
  - Columns are ordered right to left by the document's direction.
  - docling's table structure is an optional detector, never a text source.

### 3.4 The OCR route
- **Recognizers:**
  - HeOCR's released recognizers come first, for the document set they were chosen for (decision 0018).
  - Stock Tesseract `heb` is the fallback, and the baseline in every report.
- **Scope:** OCR runs on whole pages or regions.
- **Flagging:** OCR text is marked `ocr: unverified` with its confidence.
- **Region accounting:** a region where OCR returned too little for its ink is flagged; it is never passed silently.

### 3.5 Repairs, separate from normalization

**Repairs restore the characters of the source.** Examples: mojibake, private-use font codes, reversed brackets, reversed digit groups.

- **The rule list is closed.** Each rule has a reason, a real example and the formats it applies to.
- **Every application is logged** per block.
- **With repairs switched off,** the output is the extracted text, byte for byte.

**Normalization stays outside the package's default output**, per decision 0002.

### 3.6 Cross-checks
- **Numbers:** when two independent sources exist for a block (for example, the text layer and a reflowed table), digit strings are compared. A disagreement is flagged, never resolved by a guess.
- **Coverage:** each page reports what was read, what was taken by OCR, and what was not read.

## 4. Our code and dependencies

| Need | HeOCR code | Dependency | Licence |
|---|---|---|---|
| PDF text, boxes and rendering | Page classes, RTL line building, bidi, tables, coverage | **pypdfium2** (core) | BSD-3 / Apache-2.0 |
| Font and ToUnicode inspection | Mapping checks and repairs | **pdfminer.six** (core) | MIT |
| Images | — | **Pillow** (core) | MIT-CMU |
| OOXML | Numbering, headings, tables, notes | **defusedxml** (core) | PSF |
| OCR | Routing and region accounting | Tesseract (external, Apache-2.0); kraken with HeOCR models (`[ocr]` extra) | Apache-2.0 |
| Table and layout detection | — | docling (`[layout]` extra; code MIT, layout weights Apache-2.0 or CDLA-Permissive-2.0) | Permissive |
| DOC, RTF and ODT | — | LibreOffice (external, optional) | MPL-2.0 |

**Not used as dependencies:**
- PyMuPDF and pymupdf4llm, because of AGPL.
- Poppler, because of GPL.
- python-bidi, because of LGPL; Python's own `unicodedata` is enough for our bidi code.
- Surya's weights, because of decision 0014.

The tools excluded for their licences may still run as comparison baselines in the benchmark (§5), because they ship nothing.

**Code to port.** Both codebases have pieces worth taking, under the terms in §9, item 4:
- **From the volunteer's repository:**
  - the repair rules;
  - the measures that need no reference (§5.2);
  - the Word handling, as a specification for our own DOCX code.
- **From the production pipeline:**
  - format identification;
  - the text-layer warning flags;
  - RTL word-line building;
  - its rule for when an alternative reading order is safe to use.

## 5. The benchmark (D-bench)

Evaluation owns it (decision 0017). It has three layers, and every layer is reported per format and per class.

### 5.1 Synthetic documents with exact gold
- **Sources of text:** text we already may use, namely public-domain and Wikisource text, plus synthetic tender-like structure (numbered sections, tables, amounts, dates).
- **Formats:** each document is rendered to DOCX with real automatic numbering, and to PDF in every class in §3.3:
  - a correct layer;
  - visual order;
  - broken ToUnicode;
  - private-use fonts;
  - a garbage OCR layer;
  - image only, through hocrsyngen's degradations;
  - digits drawn as images;
  - spreads.
- **What this gives:** exact gold for every case, with no rights questions and no limit on size.

### 5.2 Real documents, with measures that need no reference
These are the volunteer's measures:
- **Reversed word pairs:** the order of each pair of adjacent words, checked against two independent sources.
- **Reversed amounts:** an amount that starts with `000,`.
- **Split words** per 1,000 words.
- **Separated geresh marks.**
- **Glued letters and digits.**
- **Dictionary hit rate** on OCR text.
- **Section numbers in DOCX**, checked against the numbering the document itself defines.

The documents form a private internal corpus for internal evaluation only (§9, item 5).

### 5.3 Real documents with human-reviewed references
- A small set, reviewed through heocr-review.
- For the OCR route, the existing new-printed sets serve.

### 5.4 Measures and baselines
- **Measures:**
  - character and word error in reading order (`line_fold_v1`);
  - section-number accuracy;
  - table cells, by text and position;
  - exact numbers and amounts;
  - **silent loss:** gold characters that are neither in the output nor inside a flagged region;
  - flag precision.
- **Baselines:** stock Tesseract, docling, markitdown, pymupdf4llm, and the production tender pipeline.
- **Release gate:** `heocr` ships when, on every format and class, it beats or ties every baseline. Any aggregate states its weights (decision 0018, §5).

## 6. Output contract

`heocr_document.v1` is a JSON file with:
- **document:** sha256, format and producer;
- **pages:** index, class, signals and coverage;
- **blocks:** each a text, heading, list item, table or figure, with:
  - text, or cells;
  - bbox;
  - source: text layer, OCR or office XML;
  - tool and version;
  - repairs and flags.

No local paths are recorded, following heocr-engine's prediction contract.

## 7. Milestones (notation `D`, if accepted)

| Milestone | Content |
|---|---|
| **D1** | Repository, contract and CLI; file-type detection; DOCX with numbering and headings; T1 PDF pages; D-bench v0 (synthetic DOCX and T1/T2 PDF) |
| **D2** | All PDF page classes; repairs; the OCR route with stock Tesseract and HeOCR recognizers; coverage accounting |
| **D3** | Tables (PDF and office); number cross-checks |
| **D4** | DOC, RTF and ODT through LibreOffice; images; spreads and columns; PPTX and XLSX |
| **D5** | First PyPI release, after the §5.4 gate |

## 8. Risks

- **Scope.** "Any document" has no end. The release gate is per format, so a format ships only when it wins, and the others say "unsupported", not "best effort".
- **Reading order.** The production pipeline's own audit names reading order as its largest error class. Ambiguous cases are flagged, not guessed, and the flag rate is measured.
- **Dependency on external binaries.** Tesseract and LibreOffice must be installed separately. The core runs without them, and says which route it could not take.

## 9. Decisions needed from the maintainer

1. **Name and home.** `heocr` on PyPI, in a new repository `HeOCR/heocr`, Apache-2.0. *Recommended.*
2. **No copyleft in the package.** No AGPL, GPL or LGPL Python dependencies; PyMuPDF and Poppler are out. Copyleft tools may run only as benchmark baselines. *Recommended.*
3. **Optional external tools.** Tesseract and LibreOffice may be used when the user has them installed, and are never bundled. *Recommended.*
4. **Code from Adanim.**
   - **Volunteer's repository:** the maintainer released it for reuse on 2026-11-16, and will add the licence file himself. *Decided.*
   - **Production pipeline:** does the same release cover its code (`adanim-govil-scraper`, `tendex_l4/`)?
5. **Real government documents in D-bench.** *Decided by the maintainer on 2026-11-16:* they form a private internal corpus, used for internal evaluation only.
   - The corpus is never published.
   - It lives with HeOCR's restricted evaluation material, not in a public repository.
   - It is never used for training.
6. **Who builds it.** A new team role, `pipeline[…]@heocr/opensource`, in its own session, reviewed by the lead. Evaluation builds D-bench.
7. **Vision-language models.** They stay out of v1. Later, they may come in only as an optional route with open weights that pass decision 0014, with a check of every output word against the text layer where one exists.
