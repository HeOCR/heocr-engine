# 0008 — First trained segmenter: from scratch, licence pending, typed regions, heuristic reading order

- Status: accepted
- Date: 2026-11-03
- Decided by: HeOCR team lead, under delegation from the maintainer; written by the R4b author

## Context

R3b showed that HeOCR's own recognizer reads true line polygons almost perfectly (held-out CER about 0.008), but end to end with Kraken's default `blla` segmenter its CER is 0.29 on seed-101 and 0.40 on held-out pages. `blla` splits lines and mixes their reading order. R4 trains a segmentation model on hocrsyngen pages with `ketos segtrain`, which learns baselines and region classes from PAGE XML.

The obvious shortcut is to fine-tune `blla` itself. It is Apache-2.0 (decision 0006), so licensing would allow it. But a fine-tuned model would inherit `blla`'s mostly Latin-script handwriting training, which makes the comparison against `blla` less clean and makes it harder to say what the new model learned from HeOCR data.

## Decision

- **Train from scratch,** in the same way as decision 0007. The R4 segmenter starts from randomly initialised weights with ketos 7.0.2's default segmentation network. No `blla` or other third-party weights are loaded, and the record validator rejects `-i`, `--load`, `--resume` and `--resize` in the training command. Fine-tuning `blla` can be reconsidered later in a new record.
- **Training data is project-synthetic.** Pages come from hocrsyngen batches (`PROJECT-SYNTHETIC`). The record pins the annotation, manifest and corpus sha256s.
- **What is trained:**
  - **Baselines** of every physical line, with one line type (`default`). Baselines are the typographic baseline (the bottom line location). Stamp and marginalia lines are trained, because their text is really drawn.
  - **Line polygons:** `blla` computes them from the baselines at inference. The polygons in the PAGE XML are written for completeness; segtrain trains on baselines and region areas.
  - **Regions,** typed with the hocrsyngen region name (`title`, `body`, `table_cells`, `stamp_area`, `margin`, …) through PAGE `custom="structure {type:…;}"`. Until hocrsyngen emits region polygons (hocrsyngen S11a), a region is the bounding box of its lines' polygons, one per region name per page (`region_geometry: "line_polygon_bbox"`). Once region polygons are in the sidecar, a later slice uses them and the record says so.
- **Reading order at inference** is unchanged from R3: `heocr-engine kraken` runs `kraken segment -bl` without `-d`, so kraken orders lines with its heuristic `polygonal_reading_order` and the `horizontal-lr` column hint. Lines are grouped by detected region, ordered within a region, and regions are then ordered. The model has no neural reading-order head (that would be `ketos rotrain`). The record states this in `segmentation.inference`. Changing the inference reading order is a separate decision, informed by the R4a diagnostics.
- **The model's own licence is `Needs verification` with the maintainer.** Every segmentation training-run record carries `model_licence.status: "Needs verification"` and `published: false`.
- **No publication.** Trained weights are not committed, uploaded, attached to releases or pushed to model repositories (ketos `publish` included). Release is the maintainer's call.

## Consequences

- R4 numbers compare cleanly with R3b: the same R3b recognizer and the same scored batches, and only the segmentation model changes.
- The segmenter learns only hocrsyngen layouts, fonts and degradations, which are the same as those of the synthetic test batches. Its scores say nothing about real pages (decision 0004).
- If the maintainer later chooses a licence, a new decision record states it; this record's `Needs verification` outcome is superseded rather than edited.
