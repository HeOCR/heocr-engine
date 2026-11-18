# 0024 — Use-case benchmarks for modern printed Hebrew: tenders and welfare inspection reports

- Status: accepted
- Date: 2026-11-18
- Decided by: the maintainer (Shay Palachy Affek), 2026-11-18, in the heocr-lead session; written by `lead[claude/claude-code#shay-macbook-m4]@heocr/opensource`
- Builds on: 0017 (per-domain evaluation; modern print first), 0021 (third-party engines in evaluation), 0023 (open by default, and its inherited-restriction exceptions)

## Decision

1. **Use-case benchmarks.** Beyond the per-domain tables, HeOCR reports a few named, real use cases. Each gets one headline: how good HeOCR is against the next best tool on that kind of document. The first two are both modern printed Hebrew:
   - **UC-T, government procurement tenders.** These come from the private government document corpus HeOCR already holds, the one decision 0023 names. eval uses the human-checked pages it already has as the first set, and grows it later.
   - **UC-W, welfare inspection reports.** These are the inspection reports of welfare frameworks that the Israeli Ministry of Welfare publishes on Gov.il. The reference is the manual extraction that expert analysts made for a few hundred of these reports, in a partner project.

2. **Legal basis.** In the maintainer's ruling, benchmarking on these documents is research and fair use under the Israeli Copyright Act 2007, s.19. Nothing from the documents is reproduced: only aggregate scores are published. The UC-W reports themselves are public official documents.

3. **Restrictions.** These are inherited, so decision 0023's exception for restrictions we inherit applies:
   - The documents, the references and every reader's raw output stay on the maintainer's machine. They never go to a remote machine, a third-party API, a repository or a release.
   - Only aggregates are published: per-engine scores with n and 95% intervals. No per-document scores, text, images, field values or identifiers are published.
   - None of it is ever used for training. Both sets become official decontamination (CLEAN) targets, so no training input may overlap them.
   - Public text describes the sets as in item 1 and names no partner organisation, project or person. It says the references were made by expert human analysts and are not released, and why.

4. **Measures.**
   - **UC-T:** the same page and line measures as modern print (0017), under `line_fold_v1`.
   - **UC-W:** the analysts' references are structured fields, not full transcriptions. The primary measure is field-value recall: the share of reference field values found in a reader's text after a fixed normalisation of digits, dates, spacing and punctuation. eval specifies and registers the normalisation before scoring. Where analysts transcribed a running-text field, its CER is reported too.

5. **Readers.** Every reader in the documents comparison runs: heocr, Docling, MarkItDown, pymupdf4llm, and stock Tesseract (`heb`, tessdata_best), which always appears. Surya runs too, locally and scores only, under 0021. Commercial vendors are scored only under their existing permission rules.

6. **The headline.** For each use case it is HeOCR against the best other reader, with intervals. A use case where we don't win is published as it is.

## Why

Per-domain tables tell experts how we do. A named use case tells a reader whether HeOCR solves their problem. These two are document types people extract Hebrew text from daily, and we already hold human-made references for both. That makes them the cheapest honest proof of how good we are on modern printed forms.

## Follow-ups

- **eval:**
  - register UC-T and UC-W: their sets, sha256 of the reference files, and the normalisation;
  - add both to CLEAN;
  - score them after the release gate;
  - add a use-case section to the Benchmarks page and to `results.json`, aggregates only.
- **lead:** check every public text about these sets against item 3 before merging.
