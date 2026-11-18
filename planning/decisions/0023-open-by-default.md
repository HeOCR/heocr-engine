# 0023 — Open by default: no hurdles on what HeOCR publishes, and a bias to use what others publish

- Status: accepted
- Date: 2026-11-18
- Decided by: the maintainer (Shay Palachy Affek), 2026-11-18, in the heocr-lead session ("I want us to be a beacon of open data, code, use and sharing"); written by `lead[claude/claude-code#shay-macbook-m4]@heocr/opensource`
- Builds on: 0014 (every model and dataset released for any use), 0021 (third-party engines in evaluation), 0022 (htext releases by licence)

## Decision

### What HeOCR publishes

1. **No access hurdles.** HeOCR publishes nothing behind a gate. That means:
   - no gated Hugging Face repositories;
   - no click-through agreements;
   - no sign-up or request forms;
   - no access by application.
   Anyone can download anything we release, anonymously.
2. **Licences.**
   - Code and model weights are released under Apache-2.0.
   - Data we create is released under CC0 1.0.
   - CC BY or CC BY-SA is used only where a source requires it, as decision 0022 sets out.
   - We add no purpose limits, field-of-use limits, non-commercial clauses or "research only" clauses of our own.
3. **Benchmarks are fully open.** That covers the data, the gold, the scorer, every reader's settings, the raw outputs and the per-item scores. Anyone can rerun them and check our numbers.
   - **The only exceptions are restrictions we inherit and cannot waive.** Each is named on the page that reports the numbers:
     - the private government document corpus: aggregates only;
     - files derived from fonts with restricted licences (set C `lo_pdf`): aggregates only;
     - volunteers' personal data.
   - eval's withheld test split is also kept back, because publishing it would end its use as a test. That is a scientific hold, not a licence. When a test split retires, it is published.
4. **Contribution terms stay minimal.** Volunteers' contributions are dedicated under CC0. The terms ask only what CC0 and the privacy policy need.
   - Sign-in to the review site exists only so that agreement can be counted and contributions credited or deleted on request. It is never used to restrict reading what we publish.

### What HeOCR uses from others

5. **A bias to use, not to ask.** When a third party publishes data, models or code under terms that plausibly allow our use, we use them without asking first.
   - Benchmarking, and publishing per-engine scores, is research.
   - Where a licence or gate requires accepting terms, the maintainer accepts once, and the acceptance is recorded in the source's verification note.
   - We still respect every term we accept: attribution, purpose clauses, and any ban on redistribution.
6. **Limits that still hold:**
   - decision 0014's iron rule: no non-commercial (NC) or no-derivatives (ND) material in any release;
   - decision 0021's limits on third-party engines: local weights only, no API, scores only;
   - the privacy rules for personal data.
   Where a source's terms would contaminate an open release, its data stays in evaluation and out of training and releases.
7. **Asking is for opening things up.** We write to a provider to request a release, a licence change, or a collaboration. We don't write to seek permission for uses its terms already plausibly allow.

## Why

The hurdles we kept meeting came from others' terms, not ours: gated datasets, purpose-limited licences, permission requests for local benchmarking. A Hebrew OCR project is only useful to the community if anyone can take its models, data and benchmarks and build on them with no friction. Being visibly open is also how we earn the trust and contributions we will later ask for.

## Status at adoption (2026-11-18)

- All six HeOCR models on Hugging Face are ungated and Apache-2.0.
- htext ships a CC0 core, under decision 0022.
- The heocr package is Apache-2.0.
- The Benchmarks page and its `results.json` are public.
- Two things are not yet published:
  - the D-bench generators, gold and scorer: they are in heocr-restricted-eval with the private corpus and should be split out (follow-up below);
  - the review site's export of decisions: it is planned as CC0.

## Follow-ups

- **eval:** after the release gate, move the D-bench synthetic generators, gold, scorer and run outputs into a public repository. The private corpus, the test split's identity and `lo_pdf` derivatives stay restricted.
- **lead:** check new releases against item 1 before merging.
