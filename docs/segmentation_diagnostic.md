# Segmentation diagnostic

`heocr-engine diagnose-segmentation` compares the text lines a segmenter predicts with the annotated lines of a hocrsyngen batch. It answers "did the segmenter find the lines, and in which order?" without looking at recognized text.

It is a **diagnostic, not a hocrgen score**. Like the oracle-line path in [baselines.md](baselines.md), it uses the true line geometry of synthetic pages, so it can only run on hocrsyngen batches with a line-annotations sidecar. Reported OCR numbers still come from hocrgen `evaluate-references` (decision 0004).

```sh
heocr-engine diagnose-segmentation batch/line_annotations.json batch/generation_manifest.json predicted/ \
  --match polygon --output report.json
```

- `line_annotations.json` is `hocrsyngen_line_annotations.v1`. It is validated against its manifest and the page image bytes, as in `prepare-kraken-data`.
- `predicted/` holds exactly one `<page_sha256>.xml` per annotated page: PAGE XML (any PAGE namespace; `TextLine` with `Coords` and `Baseline`) or ALTO (`TextLine` with `Shape/Polygon` or `HPOS`/`VPOS`/`WIDTH`/`HEIGHT`, and `BASELINE`). `kraken -x … segment -bl` writes PAGE XML. A page may instead have a `<page_sha256>.json` geometry file from `heocr-engine kraken --api python --geometry-output` (`heocr_engine_kraken_geometry.v1`, pixel units, the annotated page's size, lines listed in `order` 0..n-1); this scores the stage's learned or heuristic line order without converting it. A missing or extra file, or a page with both an `.xml` and a `.json` file, fails the run. Files that declare a DOCTYPE or entities are rejected.
- Coordinates are final page pixels and are clamped to the page.
- The **document order** of `TextLine` elements (or a geometry file's line `order`) is taken as the predicted reading order.
- `--lines` adds per-page, per-line assignments (`pages`), for example to re-sort predicted lines into gold order.
- The report has no local paths. It records the annotation and manifest sha256 and a sha256 over the sorted (page sha256, file sha256) pairs of the predicted files.

## Matching rule

Two matchers; `--match` picks one (default `polygon`).

- **`polygon`:** both polygons are rasterized in page pixels (even-odd fill, boundary included). The score is IoU.
- **`baseline`:** baselines are compared as functions of x (predicted points are sorted by x, so right-to-left baselines are accepted). A pair is a candidate only when the mean vertical gap over 11 points of their common x range is at most 0.5 × the gold polygon's height. The score is the x-overlap divided by the x-union. Lines without the needed geometry never match.

Every pair also has two shares: how much of the predicted line overlaps the gold line, and how much of the gold line overlaps the predicted line (area for `polygon`, x-length for `baseline`).

- **One-to-one match:** greedy by descending score, ties broken by gold then predicted index, accepted at score ≥ `--threshold` (default 0.5). Precision = matched / predicted lines, recall = matched / gold lines, F1 = 2 × matched / (predicted + gold).
- A predicted line **lies in** a gold line when ≥ 0.5 of it overlaps that gold line; it **covers** a gold line when ≥ 0.5 of the gold line overlaps it.

Each gold line gets one category, first that applies:

| Category | Meaning |
|---|---|
| `matched` | One-to-one match |
| `split` | At least two predicted lines lie in it |
| `merged` | A predicted line that covers at least two gold lines covers it |
| `partial` | Some predicted line lies in it or covers it |
| `missed` | No predicted line lies in it or covers it |

Each predicted line gets one category, first that applies:

| Category | Meaning |
|---|---|
| `matched` | One-to-one match |
| `merged` | Covers at least two gold lines |
| `fragment` | Lies in a gold line that at least two predicted lines lie in |
| `partial` | Lies in or covers some gold line |
| `spurious` | Lies in and covers no gold line |

Because a matched line can also take part in a split or a merge (a short gold line swallowed by a line matched to its neighbour, say), `events` counts these without precedence: `split_gold_lines`, `split_fragments`, `merging_predicted_lines` and `merged_gold_lines`.

Each predicted line also has an `anchor` in `--lines` output: the gold line (`line_index`) it lies in most, or `null`.

## Reading order

Over the one-to-one matched lines of each page:

- gold order is `logical_line_index`, then `line_index`; lines outside `logical_order` (index `null`) come last;
- `kendall_tau` is (concordant − discordant) / (concordant + discordant) over all pairs of matched lines, summed over pages before dividing;
- `adjacent_kept_fraction` is the share of consecutive gold lines whose predicted lines keep their order;
- `pages_scored` counts pages with at least two matched lines, and `pages_in_order` those with no discordant pair.

Order among unmatched lines (splits, merges) is not scored here. Re-sorting predicted lines into gold order and scoring the text with hocrgen measures it end to end.

## Report

`heocr_engine_segmentation_diagnostic.v1`, with `diagnostic_only: true`. `overall` and `by_template` (the manifest's `template_id`) each hold `pages`, `gold_lines`, `predicted_lines`, the `gold` and `predicted` category counts, `events`, `precision`, `recall`, `f1` and `order`. Ratios are rounded to four places and are `null` when undefined.
