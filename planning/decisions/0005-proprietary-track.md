# 0005 — Proprietary and LLM engines

- Status: accepted
- Date: 2026-11-01
- Decided by: HeOCR team lead, under delegation from the maintainer

## Decision

heocr-engine contains no proprietary, paid-service, network or LLM code. Outputs from such systems (for example Transkribus, GPT-4o, or a contributor's LLM post-correction) may be accepted as prediction files through `validate-predictions` with `track: proprietary`. They are reported separately and never mixed into open-track results.

## Consequences

- Every prediction and every `pipeline[]` stage carries `track`. A prediction is `open` only if every stage is `open`.
- Open-track stages must declare `requires_network: false`; the stage runner refuses anything else.
