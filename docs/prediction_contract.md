# Prediction contract: `heocr_engine_prediction.v1`

One JSON object per page image, UTF-8, written without NaN or infinity. The contract describes what an engine produced and how; it is not a statement of accuracy or reading-order correctness.

## Fields

| Field | Required | Meaning |
|---|---|---|
| `schema_version` | yes | `"heocr_engine_prediction.v1"`. |
| `page_id` | yes | `"sha256:"` plus `input.sha256`. A content id, not a dataset id: consumers map it to their own item and page ids explicitly. |
| `input` | yes | `sha256` (64 lowercase hex characters of the exact image bytes processed), `width` and `height` in pixels (positive integers). |
| `track` | yes | `"open"` or `"proprietary"`. A prediction is `open` only when every producing stage is open source and network-free (decision 0005). Proprietary predictions are reported separately and never mixed into open-track results. |
| `engine` | yes | Object with at least `name` and `version` strings, identifying the producer. Engine-specific provenance (executable and model hashes, settings) may be added. No local paths. |
| `text` | yes | Raw UTF-8 text as produced, expected in Unicode logical order. No normalization, bidi reversal, whitespace folding or other transform is applied or assumed (decision 0002). |
| `words` | yes | List, possibly empty. Each word has `text`, `confidence` (0–100, or `null` when the producer gives none), `bbox` `[x, y, width, height]` in input pixels with top-left origin and exclusive right/bottom edges, and `geometry_status` (`valid` for positive area, `degenerate` for zero width or height). Words and `text` are separate outputs and need not align. |
| `pipeline` | no | Ordered list of the stages that ran, described below. Absent for a single-stage engine whose `engine` block is complete provenance. |

Producers must not record source, model, executable or temporary paths, and should not put sensitive text in predictions that will be shared.

## `pipeline[]` stage records

| Field | Required | Meaning |
|---|---|---|
| `kind` | yes | `preprocess`, `segment`, `recognize` or `postcorrect`. |
| `name`, `version` | yes | Stage identity. |
| `track` | yes | `open` or `proprietary`. If any stage is `proprietary`, the prediction's `track` must be `proprietary`. |
| `deterministic` | yes | Whether the same input and artifacts give the same output. |
| `requires_network` | yes | Must be `false` for every `open` stage. |
| `license` | no | SPDX expression of the stage implementation, or `null` if unknown. |
| `artifacts` | no | List of `{ "role", "sha256" }` for models, executables or dictionaries the stage loaded. |
| `config_sha256` | no | SHA-256 of the stage's canonical JSON configuration. |
| `details` | no | Object with stage-specific provenance, such as Tesseract's `psm`. No paths. |

A post-correction stage that deliberately changes text is recorded here as `postcorrect`; it is never a hidden normalization.

## Compatibility

Files written by the PR #1 baseline carry `schema_version: "1.0"` and no `track`. Readers treat them as v1 with `track: "open"` and no `pipeline`. New output always uses the v1 id.

## Example

```json
{
  "schema_version": "heocr_engine_prediction.v1",
  "page_id": "sha256:<64 hex>",
  "input": {"sha256": "<64 hex>", "width": 1200, "height": 1600},
  "track": "open",
  "engine": {"name": "tesseract", "version": "tesseract 5.5.3", "executable_sha256": "<64 hex>",
             "models": [{"language": "heb", "sha256": "<64 hex>"}], "psm": 3},
  "text": "שלום 123\n",
  "words": [{"text": "שלום", "confidence": 91.5, "bbox": [2, 3, 10, 8], "geometry_status": "valid"}]
}
```
