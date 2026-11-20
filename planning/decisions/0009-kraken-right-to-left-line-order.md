# 0009 — Kraken segmentation orders lines right to left

- Status: accepted
- Date: 2026-11-03
- Decided by: HeOCR team lead, under delegation from the maintainer; written by the R4a author

## Context

`heocr-engine kraken` ran `kraken segment -bl` without `-d`. Kraken then orders lines with `polygonal_reading_order` and its default `horizontal-lr` hint, so lines that share a row are read left to right. On Hebrew pages this reverses the three signature boxes and the fragments of a split line.

Decision 0008 kept that order for the first trained segmenter and left a change to a separate decision informed by R4a. R4a (`docs/baselines.md`) measured the change: line geometry is identical, and only the order moves.

- Kendall τ over matched lines: 0.843 → 0.838 on seed-101 and 0.676 → 0.811 on held-out.
- R3b + `blla` overall `primary.v1` CER: 0.286 → 0.255 and 0.405 → 0.358.

## Decision

- `heocr-engine kraken` ties the segmentation direction to `--base-dir`:
  - `R`, the default, passes `-d horizontal-rl`;
  - `L` passes `-d horizontal-lr`;
  - `auto` passes no `-d`, which keeps Kraken's own default.
- `--text-direction` (or `"text_direction"` in a pipeline config) overrides it.
- The direction is recorded in the stage `details` (`null` for Kraken's default) and `config_sha256`. Predictions without `text_direction` (R2a, R3b) used Kraken's default, `horizontal-lr`.
- A segmentation training record's `segmentation.inference.text_direction` states `horizontal-rl`. Records written before this decision state `horizontal-lr`, which was correct for them.

## Consequences

- New Kraken predictions are not directly comparable with R2a and R3b numbers, because the line order changed. The R4a section gives the size of the change.
- This supersedes only the reading-order clause of decision 0008. The heuristic `polygonal_reading_order` stays, and there is still no neural reading order.
