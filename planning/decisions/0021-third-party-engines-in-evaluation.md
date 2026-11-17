# 0021 — Third-party OCR engines in HeOCR's evaluations: Surya runs locally for research

- Status: accepted
- Date: 2026-11-18
- Decided by: the maintainer (Shay Palachy Affek), 2026-11-18, in the heocr-lead session; written by `lead[claude/claude-code#shay-macbook-m4]@heocr/opensource`
- Serves: decision 0017 (per-domain evaluation) and the public Benchmarks page

## Decision

1. **Surya joins HeOCR's comparisons of OCR engines.**
   - Surya OCR by Datalab is evaluated by running its published model weights locally, under the weights licence's research-use terms.
   - It is never run through Datalab's hosted API, whose terms treat benchmark results as confidential.
2. **Conditions.**
   - **Pinned:** the model repository and commit, the package version and the licence file's checksum are recorded with every run.
   - **Scoring only:** Surya's output is used only to score it. It is never training data, labels, pseudo-labels, review suggestions or a draft reference.
   - **Not redistributed:** neither the weights nor raw outputs are redistributed, and raw outputs stay out of public repositories.
   - **Attributed:** every publication credits "Surya OCR by Datalab", with the model version and links to the model and its licence.
   - **Same publication rule:** Surya's scores are published under the same rule as every other engine, only after the human-reviewed references they are scored against exist.
3. **Unchanged:** an engine whose terms require the vendor's written consent before benchmarking is evaluated only with that consent, in writing.

## Why

Readers of HeOCR's benchmarks should see the open engines they are likely to use. Running Surya's published weights locally, for scoring only, matches the research use its licence and its publisher's documentation describe.
