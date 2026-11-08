# 0013 — A recognizer may be fine-tuned from a recognizer this engine trained

- Status: accepted
- Date: 2026-11-07
- Decided by: HeOCR team lead, under delegation from the maintainer; written by the S16b ablation author
- Amends: decision 0007's "Train from scratch" clause, for recognizers only.

## Context

Decision 0007 made every recognizer start from random weights. Its reason was licensing: fine-tuning BiblIA_01 (CC-BY-SA-4.0) would make the new weights an adaptation under ShareAlike. The record validator enforced this by rejecting any train command that loads weights.

S16b asks whether real-glyph synthetic book pages (hocrsyngen `compose-glyph-pages`) lower the recognizer's error on real scanned print. The cheap, controlled way to ask is to continue training R3h on each candidate data mix with the same line budget and epochs. Retraining from scratch would take about 6 hours per arm and change two things at once.

## Decision

- **A recognizer may start from a recognizer that heocr-engine trained.** `train-kraken --base-model M --base-record R` loads `M` with `ketos train -i M --resize union` (or `new` / `fail`).
- **The base is pinned and checked.** `R` must be a valid `heocr_engine_training_run.v1` recognition record, and `M`'s sha256 must equal `R`'s `output.model_sha256`. Since `R` must itself be valid, every model in the chain is either from scratch or a checked fine-tune. No third-party weights can enter, which keeps 0007's reason intact.
- **The record says so.** `init` becomes `{kind: "fine_tune", base_model_sha256, base_record_sha256, base_init, resize}`, and the train command must load exactly `<base_model>` with `-i` and the recorded `--resize`. `--resume` stays rejected. Segmentation and reading-order runs stay from scratch.
- **Licence and publication are unchanged.** A fine-tuned model's record carries `model_licence.status: "Needs verification"` and `published: false`, as 0007 requires. Publishing any of them is the maintainer's call.

## Consequences

- Ablations can compare data mixes from a shared, released starting point.
- A fine-tuned model inherits its base's training data, so its record must be read together with the base record that `base_record_sha256` names.
- Comparing fine-tuned arms on a real scored set, such as R3i on E2d3d, is an ablation diagnostic under decision 0012 rule 3. It answers a data question; it never selects an arm or checkpoint for release.
