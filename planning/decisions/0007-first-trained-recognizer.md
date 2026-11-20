# 0007 — First trained recognizer: from scratch, licence pending, blla segmentation

- Status: accepted
- Date: 2026-11-02
- Decided by: HeOCR team lead, under delegation from the maintainer; written by the R3a author

## Context

R3 trains HeOCR's first recognition model with Kraken's `ketos` on synthetic hocrsyngen pages. The obvious shortcut is to fine-tune BiblIA_01, the R2 Kraken baseline's recognizer. BiblIA_01 is CC-BY-SA-4.0 (decision 0006). Weights fine-tuned from it would be an adaptation, so ShareAlike would apply to the new model. Whether ShareAlike also reaches predictions is still `Needs verification` (decision 0006).

## Decision

- **Train from scratch.** The R3 recognizer starts from randomly initialised weights with ketos's default network unless a later record says otherwise. No BiblIA_01 or other third-party weights are loaded, so CC-BY-SA-4.0 does not reach the model through its weights. `heocr_engine_training_run.v1` records `init: "from_scratch"`, and the record validator rejects a training command that loads weights.
- **Training data is project-synthetic.** Pages come from hocrsyngen batches (`PROJECT-SYNTHETIC`), rendered from a project-authored text corpus with fonts that hocrsyngen ships. The record pins the annotation, manifest and corpus sha256s.
- **The model's own licence is `Needs verification` with the maintainer.** This record does not choose a licence for the weights. Until Shay decides, every training-run record carries `model_licence.status: "Needs verification"` and `published: false`.
- **No publication.** Trained weights are not committed, uploaded, attached to releases or pushed to model repositories (ketos `publish` included). Release is the maintainer's call.
- **Segmentation stays `blla`** (Apache-2.0, version DOI 10.5281/zenodo.14602569, sha256 in decision 0006) for R3 inference. Training data carries baselines and polygons so that recognition training matches baseline segmentation. Training a segmentation model is out of scope for R3.

## Consequences

- R3 numbers are comparable to the R2 baselines: same blla segmentation, same seed-101 batch, and only the recognizer changes.
- The R3 model learns only what the synthetic pages show. Its fonts and degradations are the same as those of the synthetic test batches, so its scores say nothing about real pages (decision 0004).
- If the maintainer later chooses a licence, a new decision record states it; this record's `Needs verification` outcome is superseded rather than edited.
