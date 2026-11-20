# 0003 — `alignment_masked` is a diagnostic only

- Status: accepted
- Date: 2026-11-01
- Decided by: HeOCR team lead, under delegation from the maintainer

## Context

hocrgen's reference-aware evaluator masks excluded spans (illegible, deleted, unordered marginal) on the reference side only, and requires predictions already scoped to the included content (`hocrgen/docs/reference_evaluation.md`). Full-page engine output usually contains that excluded text.

## Decision

An alignment-based masking mode, `alignment_masked`, may be offered by the evaluator as a clearly labelled diagnostic. It never contributes to primary scores.

## Consequences for this repository

Engines produce full-page raw text and do not attempt to drop text they believe the reference excludes.
