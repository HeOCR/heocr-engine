# HeOCR model publication status

**HeOCR’s model and OCR pipeline releases are on hold.** HeOCR will publish a model or packaged OCR pipeline after a registered real held-out comparison shows that it beats the state of the art on at least one document type. See [decision 0027](../planning/decisions/0027-model-release-hold.md).

The weights are retained in private storage. This directory preserves the model cards, training provenance, licence and attribution files. Its former record identifiers are archival references. Code repositories and clean CC0 datasets remain public.

## Model documentation

| Model | Purpose | Card |
| --- | --- | --- |
| modern-v1 | Modern and office print recognition for Tesseract | [Card](modern_v1/card_body.md) |
| oldprint-v1 | Historical and rabbinic print recognition for Tesseract | [Card](oldprint_v1/card_body.md) |
| A1 | Reading order for Kraken | [Card](a1/card_body.md) |
| R4d | Baseline and region segmentation for Kraken | [Card](r4d/card_body.md) |
| R3h | Hebrew line recognition for Kraken | [Card](r3h/card_body.md) |
| R6 | Printed Hebrew recognition for Tesseract | [Card](r6/card_body.md) |
| R7 | Printed Hebrew recognition for Tesseract | [Card](r7/card_body.md) |
| R8b | Printed Hebrew recognition for Tesseract | [Card](r8b/card_body.md) |

Use a local authorized weight file to reproduce an experiment. The cards give the corresponding names and hashes. The code accepts user-supplied models.

## Archived release materials

Each folder keeps a card, hosting metadata, training record, licence and NOTICE. Keep these together when retaining an archival copy. The repository history preserves previous publication instructions. The upload and deposit helpers remain available for offline fixture tests. Production use stays on hold under the release decision.

## Training records

Kraken runs use the [heocr_engine_training_run.v1 contract](../docs/training_run_contract.md). R4d's manifest, model hash and original training filename are documented in its card. The R4d, A1 and R3h weights are used together for segmentation, reading order and recognition respectively.

### `heocr_tesseract_training_run.v1`

The Tesseract records describe the starting weights, training and selection data, label order, commands with local-path placeholders, settings, evaluation provenance, output file and SHA-256, and licence basis. The automated tests retain the model-byte pins and check path hygiene, attribution and evaluation wording.
