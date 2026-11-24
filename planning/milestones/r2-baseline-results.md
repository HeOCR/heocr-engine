# R2 — First baseline results and runtime hardening

GitHub milestone: `R2 - First baseline results and runtime hardening`. Label: `roadmap:R2`.

## Objective

Record the first scored baseline runs, then fix what those runs exposed in the runtime, so that later baselines and outside pipelines start from documented numbers and accurate failure reports.

## Slices

| Notation | Summary | Status |
|---|---|---|
| R2c1 | Register an additional OPEN held-out efficiency route to launch | accepted (decision 0030) |
| R2c | Proposal for open and closed real held-out benchmarks by category | proposed (decision 0029) |
| R2b | Experimental geometry-guarded line bidi projection, with explicit abstention and raw prediction preserved separately | implemented (PR #17) |
| R2a | First synthetic-gold results for Tesseract and Kraken in `docs/baselines.md`; `run_process` failures name the failing command; the Kraken 7.0.2 macOS exit-time crash is documented | done (PR #5) |

## Boundaries

- Results are synthetic gold only (decision 0004). No claim about real pages.
- Prediction files, images and hocrgen reports from local runs stay out of the repository; only aggregate numbers and run identities are recorded.
- Offline, deterministic tests only (decision 0005).
