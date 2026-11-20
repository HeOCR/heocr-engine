# 0017 — Separate evaluation sets per kind of Hebrew document, with character, word, line and page measures

- Status: accepted
- Date: 2026-11-11
- Decided by: the maintainer (Shay Palachy Affek), 2026-11-11, in the heocr-lead session; written by `lead[claude/claude-code#shay-macbook-m4]@heocr/opensource`
- Owner: `eval[claude/claude-code#shay-macbook-m4]@heocr/opensource` (the heocr-eval session)
- Builds on: decision 0012 (real pages with human-adjudicated references are a scored set)

## Context

The R8 diagnosis showed what the 38 audit2 pages actually measure. One rabbinic responsa print, *Hut ha-Meshulash* (4 of the 38 pages), causes about 45% of all errors. So the blended number mostly measures a domain the maintainer does not use. In his words:

> "having 45% of errors caused by one rabbinic book is bad, because I personally do not use Hebrew OCR on text with Nikkud, not to mention old Rabbinic fonts. Selecting the texts composing an eval set is a choice, and reflects a reference."

## Decision

1. **Three evaluation domains, each with its own sets and its own headline numbers.** There is no blended headline.
   - **Handwriting (H):** old and modern handwriting in one domain for now.
   - **Printed historical (P-hist):** rabbinic print and other old-style Hebrew print with unusual typefaces, including Rashi script and dense abbreviation-heavy small type.
   - **Printed modern (P-mod):** modern Hebrew documents, for example government forms, slide decks, theses, homework, government tenders, Israeli laws, inspection reports and subpoenas. **This is the maintainer's own use case.**
2. **Niqqud is a stratum, not a domain.** Pointed text is flagged and reported separately within each domain, and stays out of the P-mod headline.
3. **Four measures for every domain:**
   - **character:** CER;
   - **word:** WER;
   - **line:** exact-line rate and line CER, from line references or line-aligned matching;
   - **page:** the distribution of page CER (median, p90, and the share of pages under fixed thresholds), plus a reading-order or layout cost.
   - Intervals use cluster bootstraps over the set's source units (books, Indexes, writers, document series).
4. **Selecting a set is a documented choice.** Each set's manifest states the population it stands for, how its items were chosen and why, and what it leaves out.
5. **Decision 0012 applies inside each domain.**
   - A scored set is never used for training, tuning or selection.
   - Whole works or sources are held out.
   - A model is scored once per scored set, after selection.
   - Dev signals stay dev signals.
6. **Rights and privacy.**
   - Open sets where the rights allow.
   - Otherwise private, evaluation-only sets in `HeOCR/heocr-restricted-eval`, which publish metrics only.
   - Personal-data screening for every set.
   - Documents that carry personal data (homework, subpoenas, theses, forms filled in by people) need a donor-consent path. That goes to the maintainer before any collection, and the consent template (E1c) still needs his approval and legal review.
7. **Existing numbers stay valid as written.** The audit2 38-page results remain correct as blended results. They are re-reported per domain once the existing pages are classified, and are no longer the headline.
8. **Model direction follows the domains.** R8's rabbinic work continues as P-hist work. Training priorities are then set per domain, with P-mod first.
