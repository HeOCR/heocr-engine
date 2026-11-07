# Planning

`planning/` is the source of truth for heocr-engine milestones, task notation and decisions. Merged `main` and merged PR history decide what is done; update these files when they disagree.

## Notation

Planned work uses `R<milestone><slice>`, for example `R1a`. `R` stands for the runtime repository; the letter keeps it distinct from hocrgen's `A`–`F` phases. A slice can be split further with a digit, for example `R1b1`.

- Milestone files: `milestones/r<N>-<topic>.md`, one per milestone, listing its slices and their status.
- Decision records: `decisions/NNNN-<topic>.md`, numbered in order and never renumbered. Supersede a decision with a new record instead of editing the old one's outcome.
- GitHub: each milestone has a GitHub milestone named `R<N> - <title>` and a `roadmap:R<N>` label.

## Current milestones

- [R1 — Runtime foundations and plug-in path](milestones/r1-runtime-foundations.md) (complete)
- [R2 — First baseline results and runtime hardening](milestones/r2-baseline-results.md)
- [R3 — First trained recognizer](milestones/r3-first-trained-recognizer.md)
- [R4 — Trained segmentation](milestones/r4-trained-segmentation.md)

## Proposals

Proposals are drafts for the maintainer's decision. They decide nothing; an accepted proposal becomes a decision record.

- [Releasing HeOCR's trained weights (R3h first)](proposals/model-release.md): training inputs and licences, candidate weights licence, model card outline, hosting, sign-offs

## Decisions

| Record | Decision |
|---|---|
| [0001](decisions/0001-governance.md) | Planning notation, labels, milestones; no self-merge |
| [0002](decisions/0002-normalization-boundary.md) | Engines emit raw text; normalization profiles are evaluator-side, explicit and recorded |
| [0003](decisions/0003-alignment-masked-diagnostic.md) | `alignment_masked` scoring is a labelled diagnostic only |
| [0004](decisions/0004-scored-set.md) | Synthetic gold is the reported number; real pages are `unreviewed` diagnostics (superseded by 0012) |
| [0005](decisions/0005-proprietary-track.md) | No proprietary or network code; proprietary predictions enter as `track: proprietary` |
| [0006](decisions/0006-model-licences.md) | Kraken baseline models are user-supplied and hashed; BiblIA_01 is CC-BY-SA-4.0, `blla` is Apache-2.0 |
| [0007](decisions/0007-first-trained-recognizer.md) | The first trained recognizer starts from scratch (no BiblIA_01 weights); its licence is `Needs verification` with the maintainer; it is not published; segmentation stays `blla` |
| [0008](decisions/0008-first-trained-segmenter.md) | The first trained segmenter starts from scratch (no `blla` weights); it learns baselines and regions typed by hocrsyngen region name; inference keeps kraken's heuristic reading order; licence `Needs verification`; not published |
| [0009](decisions/0009-kraken-right-to-left-line-order.md) | `heocr-engine kraken` ties the segmentation direction to `--base-dir` (R → `-d horizontal-rl`) with an override, and records it; supersedes 0008's reading-order clause |
| [0010](decisions/0010-r3h-release.md) | R3h is released first, under Apache-2.0, licensed by "HeOCR maintainers"; OFL fonts credited but not reaching the weights; Zenodo (version DOI) and Hugging Face; supersedes 0007's licence and publication clauses for R3h only |
| [0011](decisions/0011-first-release-adds-r4d-and-a1.md) | The first release is R3h + R4d + A1 under 0010's terms, after the R3h + `blla` scores; supersedes 0010's scope and, for R4d and A1, 0008's licence and publication clauses |
| [0012](decisions/0012-real-page-scored-sets.md) | Real pages with human-adjudicated hocrgen references (e.g. E2d3d) are a scored set beside synthetic gold; pseudo-labels and silver text are dev signals only; supersedes 0004 |
| [0013](decisions/0013-fine-tune-project-recognizers.md) | A recognizer may be fine-tuned from a recognizer heocr-engine trained, pinned by model and record hash; amends 0007 for recognizers; licence and publication unchanged |
