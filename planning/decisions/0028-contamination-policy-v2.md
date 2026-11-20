# 0028 — Separate source contamination from shared text

- Status: accepted
- Date: 2026-11-20
- Decided by: the maintainer
- Amends: [0012](0012-real-page-scored-sets.md), [0017](0017-domain-separated-evaluation.md), [0025](0025-uc-w-data-split.md), [0026](0026-uc-w-private-training-infrastructure.md)

Visually distinct documents can contain the same text. This is common in religious,
literary and administrative material. Preserve those training sources when their
provenance and visual category establish separation, and disclose text exposure in the
evaluation.

## Hard exclusions

Exclude training material from the same image, scan, page, physical copy, manuscript
or print edition as a benchmark source. An alternate capture of the same document is
also excluded. Exclude synthetic renders of benchmark text. Source reservations apply
to derived crops and labels as well as original pages.

For print compared with print, a different edition of the same work in a similar
typeface remains excluded. Keep the historical-print reservations that enforce this
rule. Verify the edition and the visual distinction before clearing an exception.

## Allowed overlap

The same text may appear in training and test in different visual categories, for
example handwriting on parchment and modern printed books. A different print edition
in a clearly different typeface is also eligible. In the facility-split modern-print
benchmark, recurring form or template text across different reports is eligible
provided the benchmark and calibration report and facility exclusions pass.

## Evaluation and reporting

Verify source separation from pinned provenance before admitting the training input.
Use normalized text matching against the exact training revisions to give every
benchmark line a **text seen in training** flag. Shared text under an allowed case
sets the flag and does not cause a training drop. Record coverage and disclose where
training inventories are unavailable. Unchecked lines cannot be certified as
non-overlapping.

Report every result on **all scored lines** and on **non-overlapping lines**, with
denominators and the same scoring rules. Comparisons use the same non-overlapping lines
for all readers in the comparison. When no non-overlapping lines can be verified, report
that the subset is unavailable. The facility-split benchmark continues to publish
aggregates only.

— eval[openai/codex#shay-macbook-m4]@heocr/opensource
