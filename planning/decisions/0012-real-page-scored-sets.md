# 0012 — Real pages with human-adjudicated references are a scored set

- Status: accepted
- Date: 2026-11-08
- Decided by: HeOCR team lead, under delegation from the maintainer
- Supersedes: decision 0004

## Context

Decision 0004 made synthetic gold the only reported number because no human transcription campaign was planned (hocrgen issue #86). The maintainer has since withdrawn that constraint. hocrgen now has human-adjudicated references for 38 real printed pages: manifest `e2d3d_wikisource_printed_v5`, second-human-validated under maintainer decision 2 of 2026-11-06. R4f also uses real pages with Tesseract pseudo-labels and silver text, but only as dev signals.

## Decision

1. **Scored sets.** A number is a benchmark result when hocrgen scores it against one of:
   - synthetic gold, from governed hocrsyngen batches with known text;
   - real pages whose references are human-adjudicated in hocrgen, such as E2d3d.
2. **Dev signals.** Other real-page references are dev signals for selection, never benchmark results. These include Tesseract pseudo-labels, silver text such as Project Ben-Yehuda, a publisher's glyph layer, and unreviewed HASH or tender transcriptions.
3. **No tuning on scored real pages.** No training, tuning or checkpoint selection uses a scored real set, and whole works or Indexes are held out. A model is scored on a real scored set once, after selection. Diagnostic decompositions of already-fixed models (such as R4f step 1) are allowed, but they never feed selection.
4. **Agent review is not human review.** Agent or GPT-4o review is never labelled "reviewed" or "human".

## Consequences for this repository

- Every real-page number names its reference status and manifest.
- Earlier results labelled "synthetic gold only (decision 0004)" remain accurate as written.
