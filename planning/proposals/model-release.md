# Proposal: releasing HeOCR's trained weights (R3h first)

- Status: **proposal**, for the maintainer's decision. It decides nothing. The maintainer decided §7 items 1–5 and 7 on 2026-11-06; [decision 0010](../decisions/0010-r3h-release.md) records them, and [decision 0011](../decisions/0011-first-release-adds-r4d-and-a1.md) widens the scope to R3h + R4d + A1. The maintainer approved the three model cards (item 6) on 2026-11-06; decision 0011's note records it.
- Date: 2026-11-06
- Written by: R4b (agent contributor) at the HeOCR team lead's request; reviewed by the lead. Approval is the maintainer's.
- Scope: the R3h recognizer, and possibly the R4d segmenter with the A1 reading-order model (the deployed R4d + A1 pipeline).

Nothing here publishes, uploads or commits weights. Nothing here changes a model's licence status. Every training record keeps `model_licence.status: "Needs verification"` and `published: false` (decisions 0007 and 0008) until a new decision record supersedes those clauses. [decision 0010](../decisions/0010-r3h-release.md) does so for R3h; nothing is published until each publishing step gets the maintainer's go-ahead.

**How to read this:**
- **Evidence** is a file at a commit, a local record named by its sha256, or an upstream URL read on 2026-11-06.
- **Flags** (⚑) mark inputs whose terms are unclear or could bear on redistributing weights. They are raised for the maintainer, not decided here. Licence and rights calls are the maintainer's.

## 1. What would be released

| Model | File | sha256 | Init | Training data | Record |
|---|---|---|---|---|---|
| **R3h** recognizer (recognizer of record, `docs/baselines.md` R3h section, #31) | `best_0.9959.safetensors`, 16,167,536 bytes | `f76affa84e29536aa1d41f89d3507183c104f1620ca953fdfa5dd4b7a00ba6be` | `from_scratch` | hocrsyngen batch, seed 7201, 3,000 pages; corpus `7c2a62b8…` | `heocr_engine_training_run.v1`, validates |
| **R4d** segmenter (optional) | `best_0.8618.safetensors` | `d32cd1a8efe7354445ccfea76551cc9943ca05792c332b5865f9bec985fe7bf7` | `from_scratch` | hocrsyngen batch, seed 5101, 1,800 pages; corpus `a3f2f0db…` | `heocr_engine_training_run.v1` |
| **A1** reading order (optional) | `best_0.0000.safetensors`, 8,492 bytes | `69aa1946583bb68ddf13ef20860582f4aa982a46b2f79e38bd7d9ae20535fb56` | from scratch (no `-i`/`--load` in its command) | R4d's and R3d's training pages, re-prepared with region line types | ad hoc local record, **not** `heocr_engine_training_run.v1` ⚑ |

**What the R3h file embeds.** Its safetensors header was read on 2026-11-06. There are 34 tensors and one metadata key, `kraken_meta`, which holds:
- the codec of 117 symbols (Hebrew letters, digits, Latin `A–Z a–z`, ASCII and typographic punctuation);
- the VGSL network string (ketos 7.0.2's default recognition network);
- the fields `_kraken_min_version`, `_tasks`, `_model`, `seg_type`, `one_channel_mode`, `model_type` and `legacy_polygons`. `accuracy` and `metrics` are empty.

It holds no local paths, user names or training-data text. The R4d and A1 headers likewise hold `kraken_meta` only, with no local paths.

**What must not be released:**
- **Lightning `.ckpt` checkpoints.** R3h's `checkpoint_04-0.9959.ckpt` contains 8 local absolute-path strings. Only the converted `best_*.safetensors` should ever ship.
- **The A1 record as it stands.** It contains a local absolute path in its `command`.
- **Local data:** prediction sets, reports and run directories stay local.

## 2. Training inputs and their licences

### 2.1 Weights loaded: none from third parties

- **R3h:** `init: "from_scratch"`. The validator in `heocr_engine/training.py` (`validate_training_run`, main `5880451`) rejects `-i`, `--load`, `--resume` and `--resize`. The R3h record validates.
- **Other recognizers:** every local recognizer record has `init: "from_scratch"`: R3b, R3c, R3d, R3f s7201 and s7202, R3g and R3h.
- **R4d:** `from_scratch`, under decision 0008.
- **A1:** trained with `ketos rotrain` and no weights flag. It has no formal `init` field ⚑ (§4).
- **The one fine-tune, R3e (PR #21, `research/printed_line_transfer/`):**
  - It loaded **R3b**, HeOCR's own from-scratch weights (`0b5a0c3c…`), as a research diagnostic.
  - It also rendered with Noto Sans Hebrew (OFL-1.1), a font the released models never saw.
  - No released candidate descends from R3e. R3h is from scratch, not from R3b or R3e.
- **BiblIA_01 and `blla`:**
  - BiblIA_01 (CC-BY-SA-4.0) and `blla` (Apache-2.0) were R2 baselines only (decision 0006). Neither was loaded into any candidate.
  - CC-BY-SA-4.0 therefore does not reach the candidates through their weights (decision 0007).

### 2.2 Fonts

The font manifest at hocrsyngen `88ba5e6` (R3h's batch) is `src/hocrsyngen/data/synthetic/fonts/manifest.yaml`. It lists two fonts, and the font directory has not changed since the bootstrap commit `069490a` (#1).

Every candidate's training batch draws only these two fonts:
- R3h: 2,143 pages in Alef and 857 in Gveret Levin;
- R4d: 1,286 and 514;
- R3d: 1,714 and 686.

| Font | Packaged file (sha256) | Licence file in hocrsyngen | Upstream evidence | Notes |
|---|---|---|---|---|
| Alef Regular 1.002 | `Alef-Regular.ttf` (`a32adcc9…`) | `LICENSE-Alef-OFL.txt`: "Copyright (c) 2012, HaGilda & Mushon Zer-Aviv … with Reserved Font Name Alef", SIL OFL 1.1 | [google/fonts `ofl/alef/OFL.txt`](https://github.com/google/fonts/blob/main/ofl/alef/OFL.txt), same copyright and RFN, OFL 1.1 | ⚑ The font's own `name` table reads "Copyright (c) 2012 by Hagilda. All rights reserved." It has no licence entry; the OFL grant is only in the separate file. `fsType` 0 (installable). |
| Gveret Levin Regular 2.000 | `GveretLevin-Regular.ttf` (`05c44339…`) | `LICENSE-GveretLevin-OFL.txt`: "Copyright 2024 The Gveret Levin Project Authors", SIL OFL 1.1 | [AlefAlefAlef/gveret-levin](https://github.com/AlefAlefAlef/gveret-levin) (`OFL.txt`, OFL-1.1); [openfontlicense.org](https://openfontlicense.org) | The `name` table states OFL 1.1 with a licence URL. No Reserved Font Name found. `fsType` 0. |

- ⚑ **The manifest records no source URL, version or licence per font,** only `id`, `file`, `style` and `notes`. Provenance rests on the licence files and the `name` tables. A release card should cite both.
- ⚑ **Does the OFL reach the weights?** OFL 1.1 governs the Font Software and its derivatives. The weights contain no font data, only parameters learned from rendered page images. This proposal does not decide whether that puts them outside the OFL. It is common practice to treat it so, but the maintainer should confirm. Either way, credit both fonts in the model card. The Reserved Font Name "Alef" matters only for modified fonts, which a model release does not distribute. **Decided 2026-11-06 (decision 0010):** OFL-1.1 does not reach the weights; both fonts are credited.

### 2.3 Text corpora

**R3h's corpus.** `7c2a62b8…` (932,130 bytes) is the byte concatenation, in this order, of three packaged hocrsyngen files at `88ba5e6`. This was checked by hashing all six orders; only this one matches.

| Corpus | File (`src/hocrsyngen/data/synthetic/texts/`) | Bytes | Card (hocrsyngen `docs/`) | Licence |
|---|---|---|---|---|
| S10b train | `hebrew_lines_train_v1.txt` (`a3f2f0db…`) | 439,596 | `training_text_corpus_card.md` | CC0-1.0, project-authored; "No third-party text is included" |
| S13a train (mixed script) | `hebrew_mixed_lines_train_v1.txt` (`203df9e8…`) | 258,611 | `mixed_script_text_corpus_card.md` | CC0-1.0, project-authored; "No third-party text is included" |
| S13b train (typographic) | `hebrew_typographic_lines_train_v1.txt` (`5c385b41…`) | 233,923 | `typographic_text_corpus_card.md` | CC0-1.0, project-authored; "No third-party text is included" |

At `88ba5e6` the cards stated MIT, the repository licence. Since [HeOCR/hocrsyngen#91](https://github.com/HeOCR/hocrsyngen/pull/91) (2026-11-06, [ADR 0008](https://github.com/HeOCR/hocrsyngen/blob/main/docs/decisions/0008-cc0-for-project-authored-text-corpora.md)) the three corpora are dedicated to the public domain under CC0-1.0, and `texts/LICENSE-CC0-1.0.txt` lists the files covered. The corpus bytes are unchanged, so the sha256s above still hold. The hocrsyngen code stays MIT.

**Other candidates' corpora.** R4d trained on S10b train alone (`a3f2f0db…`). R3d, whose pages A1 also used, trained on S10b + S13a (`e4384322…`, 698,207 bytes; the same concatenation check).

**Where the text comes from.** Each card's Provenance section says the text is "original text authored by AI agents (Claude Opus 5.5 sessions run in Claude Code) for HeOCR":
- S10b on 2026-11-02, S13a on 2026-11-03 and S13b on 2026-11-04;
- each under a brief that forbade copying or close paraphrase of published sources, and real people, organisations, addresses, IDs, emails and URLs.

Overlap against eval corpora and against hocrgen's `bidi-synthetic-corpus.txt` is checked and recorded in each card. The hocrgen corpus is not vendored, only hashed. Batch manifests tag every sample `PROJECT-SYNTHETIC`: 3,000/3,000 for R3h, 1,800/1,800 for R4d and 2,400/2,400 for R3d.

- **The provider's terms for AI-authored text: resolved by maintainer decision, 2026-11-06.** The corpora are outputs of Anthropic's Claude, and the governing terms depend on the account the sessions ran under.
  - **Decision (maintainer, 2026-11-06):** "a hebrew OCR model does not count as competing." The competing-model restriction in either set of terms below does not apply to a Hebrew OCR model, so which set governed the authoring sessions no longer matters for this release.
  - [Consumer Terms](https://www.anthropic.com/legal/consumer-terms) (effective 2025-10-08):
    - §4 assigns Outputs to the user, "Subject to your compliance with our Terms".
    - §3(2) bars using the Services "to develop any products or services that compete with our Services, including to develop or train any artificial intelligence or machine learning algorithms or models".
  - [Commercial Terms](https://www.anthropic.com/legal/commercial-terms) (effective 2025-06-17):
    - §B assigns Outputs to the customer.
    - §D.4 bars accessing the Services "to build a competing product or service, including to train competing AI models".
  - **Was for the maintainer:** which terms applied, and whether a Hebrew OCR recognizer trained on these outputs falls inside either restriction. Answered by the decision above.
- ⚑ **Copyright in AI-authored text.** Whether text written by AI agents carries copyright at all varies by jurisdiction. The cards now dedicate the text under CC0-1.0, which waives whatever rights the project holds without claiming any exist. That does not restrict a weights release, but the model card should not overstate the corpus's licence.
- ⚑ **The S13a card's Provenance section.** It lists, among material the brief forbade copying, a category of non-public source material. A release card should cite the corpora's licence and authorship lines only, not that list.

### 2.4 Code that produced the data and the models

| Component | Role | Licence | Evidence | Reaches the weights? |
|---|---|---|---|---|
| hocrsyngen `88ba5e6` | Renders pages, line sidecars and degradations. Degradations are procedural; the package ships no textures or images, only the two fonts and the text files | MIT (code); the S10b, S13a and S13b text is CC0-1.0 since hocrsyngen #91 | `LICENSE` ("Copyright (c) 2026 HeOCR"); `pyproject.toml` `license = { text = "MIT" }` | Indirectly, as training images |
| heocr-engine (`55b0f7d` for R3h training) | `prepare-kraken-data`, `train-kraken`, records | MIT | `LICENSE` ("Copyright (c) 2026 HeOCR") | No code is embedded |
| Kraken / ketos 7.0.2 | Trainer; defines the network (VGSL) and the file format | Apache-2.0 | [mittagessen/kraken `LICENSE`](https://github.com/mittagessen/kraken/blob/main/LICENSE); PyPI metadata `License-Expression: Apache-2.0`; decision 0006 | ⚑ The file embeds ketos's default VGSL network *string* and kraken's metadata layout, not kraken code. Probably no obligation follows, but the maintainer should confirm whether to credit kraken in a NOTICE. |
| hocrgen (`2d3efb0`, `c8fb74e`) | Scoring only; its fixture batch is a development set, never trained on | MIT | `LICENSE` ("Copyright (c) 2026 HeOCR maintainers") | No |
| Training stack | Runtime only | torch 2.10.0 BSD-3-Clause; lightning 2.6.1 Apache-2.0; safetensors 0.7.0 Apache-2.0; shapely 2.1.2 BSD-3-Clause; Pillow 11.3.0 MIT-CMU; pyarrow 22.0.0 Apache-2.0; python-bidi 0.6.10 LGPL | Installed package metadata, 2026-11-06 | No. The LGPL python-bidi only reorders labels at training time and is not embedded. |

- ⚑ **The copyright holder is named differently.** heocr-engine and hocrsyngen say "HeOCR", hocrgen says "HeOCR maintainers". A release needs one licensor name. **Decided 2026-11-06 (decision 0010):** "HeOCR maintainers", everywhere.
- **GitHub's licence detection.** GitHub detects MIT for all three repositories (`gh api repos/HeOCR/<repo>/license` gives `spdx_id: MIT`, checked 2026-11-06). An earlier version of this note said no licence was detected. That came from `gh repo view --json licenseInfo`, which has no `spdxId` field. Nothing needs fixing.

### 2.5 Evaluation inputs (not training)

- **Evaluation batches:** seed-101 (S10c), held-out s6101, eval-mixed-heldout, eval-typo-heldout and eval-layout-heldout are hocrsyngen batches from the eval corpora, with the same two fonts.
- **hocrgen fixture:** a development set.
- **Use:** none was trained on. They affect only the numbers in a model card.
- **Real pages:** no reviewed real-page evaluation exists. Real pages are `unreviewed` diagnostics only (decision 0004), and a card should not cite them.

## 3. Candidate weights licence

Options, with trade-offs. The choice is the maintainer's. A new decision record would supersede the `Needs verification` clauses of 0007 and 0008 rather than editing them.

| Option | For | Against |
|---|---|---|
| **Apache-2.0** | Matches kraken and `blla` (decision 0006), so it fits the kraken model ecosystem. It is permissive, with an explicit patent grant, and NOTICE-based attribution can credit the fonts and kraken. It is an OSI licence, so model hubs list it cleanly | Heavier than MIT. A NOTICE file must travel with redistributions |
| **MIT** | Same as all three HeOCR code repositories, the simplest terms, and permissive | No patent grant. Attribution is only the copyright line, so font and kraken credits would be courtesy rather than terms |
| **CC-BY-4.0** | Common for models on the kraken/HTRMoPo Zenodo repository, and attribution is explicit | Not written for software or weights. No patent grant. CC itself advises against CC licences for software |
| **CC-BY-SA-4.0** | Mirrors BiblIA_01, and keeps derivatives open | ShareAlike deters reuse. The open question in decision 0006 (does SA reach outputs?) would now attach to HeOCR's own model. Nothing upstream requires it, since no SA input was used |
| **CC0-1.0** | Maximum reuse | No attribution, not even for the fonts' authors. A permanent DOI deposit could not later add conditions |
| **OpenRAIL-M or another use-restricted licence** | Lets use restrictions be stated | Not open source. Uncommon in OCR. Adds terms users must interpret. Nothing in the inputs calls for it |

**Proposed candidate, for discussion: Apache-2.0 for the weights.** Its NOTICE would:
- credit Alef (HaGilda & Mushon Zer-Aviv, OFL-1.1) and Gveret Levin (The Gveret Levin Project Authors, OFL-1.1);
- credit kraken (Apache-2.0);
- state that the training text is AI-authored and synthetic.

The fallback is MIT, if one licence across all HeOCR artefacts matters more.

**Decided 2026-11-06:** Apache-2.0 for the weights ([decision 0010](../decisions/0010-r3h-release.md)).

## 4. What must be fixed before any release

- **A1 has no `heocr_engine_training_run.v1` record.** It lacks `init`, `model_licence`, and corpus and manifest pins, and its `command` holds a local path. To release R4d + A1, write a proper record first: re-validated, with no local paths.
- **One copyright-holder name** across the licence, NOTICE and card (§2.4).
- **A sanitised training record** to ship beside each model. The R3h and R4d records contain no local paths; they use placeholders such as `<ketos>`. Check again at release time.
- **A pinned version DOI** (if Zenodo), cited by version and never by concept DOI (decision 0006).

## 5. Model card outline (R3h)

1. **Summary.** Kraken 7.0.2 recognition model (VGSL, 117-symbol codec) for printed and handwriting-style modern Hebrew document lines with digits, Latin letters and typographic punctuation. sha256 `f76affa8…`.
2. **Intended use.**
   - Line recognition inside a Kraken baseline-segmentation pipeline: the R4d segmenter with A1 reading order, or `blla`. Also on sidecar polygons and Tesseract line boxes.
   - It is a research baseline. It is not for unsupervised transcription of real documents.
3. **Out of scope.**
   - Accuracy claims on real scans; no reviewed real-page evaluation exists (decision 0004).
   - Medieval and liturgical scripts, niqqud (no niqqud in R3h's training text or its codec) and non-Hebrew documents.
4. **Training data.**
   - Synthetic only: 3,000 hocrsyngen pages over seven templates, giving 47,633 training lines and 2,706 validation lines.
   - Two OFL fonts (Alef, Gveret Levin).
   - AI-authored text (S10b + S13a + S13b), with no third-party text.
   - Line geometry: 3/4 Kraken polygonizer, 1/8 sidecar polygon, 1/8 padded box (`--rect-pad -0.14`).
5. **Training procedure.**
   - From scratch, with ketos defaults. Seed 42, mps.
   - Early stopping after 8 epochs, best epoch 4, val_accuracy 0.9959 on mixed geometry.
   - Not deterministic.
   - heocr-engine `55b0f7d`. Cite the training-run record.
6. **Evaluation.** Synthetic gold, `primary.v1` CER, hocrgen; from `docs/baselines.md` R3h (#31).

   | Batch, lines | CER |
   |---|---|
   | seed-101, sidecar polygons | 0.014 |
   | held-out, sidecar polygons | 0.004 |
   | seed-101, Tesseract lines | 0.116 |
   | held-out, Tesseract lines | 0.088 |
   | seed-101, R4d + A1 | 0.020 |
   | held-out, R4d + A1 | 0.010 |
   | hocrgen fixture (development set), R4d + A1 | 0.130 |
   | eval-mixed-heldout, R4d + A1 | 0.017 |
   | eval-typo-heldout, R4d + A1 | 0.009 (269 of 308 typographic marks kept) |
   | eval-layout-heldout, R4d + A1 | 0.124 |

   Each figure has its paired interval against R3d in #31. The intervals resample pages, not training runs, and there is one training run.
7. **Known weak spots** (from #31):
   - **Ledger pages:** 2,432 of 2,611 edits on eval-layout-heldout.
   - **`handwritten_note_heavy_wear` on eval-layout-heldout:** 37 → 60 edits against R3d, mostly Latin letters.
   - **Gershayim:** written as ASCII `"` (8 substitutions, plus 11 stray `"`).
   - **Typographic marks:** right single quote kept 0 of 5, en dash 20 of 26.
   - **Seed-101 `printed_letter` under R4d + A1:** slightly behind R3f s7201.
   - **Synthetic gap:** the fonts and degradations are those of the eval batches, so scores overstate real-world accuracy.
8. **Licence and attribution:** per the decision (§3), with font and kraken credits.
9. **Provenance and reproduction:** batch, corpus and manifest sha256s; hocrsyngen `88ba5e6`; heocr-engine `55b0f7d`; kraken 7.0.2.
10. **Contact and how to report issues.**

The R4d and A1 cards would follow the same outline, using the R4d and R4e sections of `docs/baselines.md`.

## 6. Where to host

| Venue | For | Against |
|---|---|---|
| **Zenodo through `ketos publish`** (kraken's model repository, [HTRMoPo](https://github.com/HtrMoPo/HTRMoPo) schema, [kraken 7.0 model docs](https://kraken.re/7.0/user_guide/models.html)) | Gives a version DOI, which fits decision 0006's pinning by version DOI. `kraken get` can fetch it. The record is a Markdown card with YAML metadata (`license`, `authors`, `language`, `script`, `metrics`). It is where `blla` and BiblIA_01 live | **Permanent: the deposit "cannot be changed or deleted later".** Repository inclusion needs community approval. A wrong licence or card cannot be withdrawn |
| **Hugging Face Hub** | A model card with licence metadata. Versions can be edited, gated or deleted | Not a kraken source: kraken's 7.0 docs describe only Zenodo DOIs for `kraken get`. No DOI by default |
| **GitHub Release on heocr-engine** | Sits next to the code version that trained the model, with the checksums in the release notes | No model card conventions. A DOI only through Zenodo–GitHub integration |

**Proposal.**
1. Approve the card and licence text.
2. Do a dry run on Zenodo's sandbox, if `ketos publish` can target it, or by hand on a private Hugging Face repository.
3. Deposit on Zenodo once, with a version DOI.
4. Optionally mirror on Hugging Face, linking to the DOI.

Each step is a separate go-ahead from the maintainer.

## 7. What the maintainer must sign off

1. **The provider's terms for the AI-authored corpora (§2.3):** which terms governed the authoring sessions, and whether training and releasing these weights is consistent with them. **Decided 2026-11-06:** "a hebrew OCR model does not count as competing", so the competing-model restriction in either set of terms does not apply. This item no longer gates the rest.
2. **The weights licence (§3),** recorded in a new decision record that supersedes 0007's and 0008's licence clauses. **Decided 2026-11-06:** Apache-2.0. [decision 0010](../decisions/0010-r3h-release.md) supersedes 0007's licence and publication clauses for R3h; 0008 still applies to R4d and A1.
3. **The font position (§2.2):** that weights trained on OFL-rendered images can be released under that licence, and the attribution wording. **Decided 2026-11-06:** OFL-1.1 does not reach the weights, which contain no font data. Both fonts are credited in the model card and the NOTICE: Alef (HaGilda & Mushon Zer-Aviv) and Gveret Levin (The Gveret Levin Project Authors).
4. **The licensor name (§2.4)** and the NOTICE text. **Decided 2026-11-06:** "HeOCR maintainers", everywhere. The NOTICE text is drafted for the maintainer's review.
5. **Scope:** R3h alone, or with R4d + A1. If A1 is included, it first needs a proper training record (§4). **Decided 2026-11-06:** R3h alone for the first release. R4d + A1 come later, and A1 first needs a proper training record. **Changed 2026-11-06 ([decision 0011](../decisions/0011-first-release-adds-r4d-and-a1.md)):** after R3h was scored with `blla` (CER 0.168–0.498 against 0.009–0.130 with R4d + A1), the maintainer widened the first release to R3h + R4d + A1, under the same terms. A1 gets a proper training record first.
6. **The model card text,** with its evaluation numbers and weak spots, reviewed by a human. Agents do not stand in for human reviewers. **Decided 2026-11-06:** the maintainer approved the three cards (`release/{r3h,r4d,a1}/card_body.md`) as they stand on main at `952e5b5`; decision 0011's note pins them by sha256. Only the reserved DOIs are added later.
7. **The hosting venue and account (§6),** accepting that a Zenodo deposit is permanent. **Decided 2026-11-06:** as many venues as make sense, starting with both Zenodo (with a version DOI; the team lead chose `htrmopo publish` with the release directory as the tool, see decision 0010's note) and Hugging Face Hub. The maintainer accepts that the Zenodo deposit is permanent and has no intention of deleting or changing deposits. More venues may be added later. **Still open:** which accounts or organisations to publish under on Zenodo and on Hugging Face.
8. **Each publishing action,** one by one: sandbox run, deposit, mirror.

Item 8, and the accounts under item 7, stay open.
