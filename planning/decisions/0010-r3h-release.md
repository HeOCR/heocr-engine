# 0010 — Releasing R3h: Apache-2.0 weights, fonts credited, Zenodo and Hugging Face

- Status: accepted
- Date: 2026-11-06
- Decided by: the maintainer (Shay), 2026-11-06; written by R4b at the HeOCR team lead's request
- Supersedes: for the R3h recognizer only, decision 0007's licence clause (`Needs verification`) and its "No publication" clause. Decision 0008 is unchanged.

## Context

The proposal [Releasing HeOCR's trained weights](../proposals/model-release.md) lists the inputs to the trained models with their licences, and eight sign-offs for the maintainer (§7). R3h is the recognizer of record (`docs/baselines.md`, R3h section, #31): `best_0.9959.safetensors`, sha256 `f76affa84e29536aa1d41f89d3507183c104f1620ca953fdfa5dd4b7a00ba6be`, trained from scratch on hocrsyngen pages.

Its training text (S10b, S13a and S13b) was authored by Claude Opus 5.5 sessions. Since hocrsyngen #91 ([ADR 0008](https://github.com/HeOCR/hocrsyngen/blob/main/docs/decisions/0008-cc0-for-project-authored-text-corpora.md)) it has been dedicated to the public domain under CC0-1.0. The pages are rendered in two OFL-1.1 fonts.

## Decision

The maintainer decided these sign-offs on 2026-11-06. Item numbers are those of proposal §7.

- **Item 1, the provider's terms.** "A hebrew OCR model does not count as competing." The competing-model restriction in Anthropic's Consumer and Commercial Terms does not apply to a Hebrew OCR model.
- **Item 2, weights licence: Apache-2.0.**
- **Item 3, fonts.**
  - OFL-1.1 does not reach the weights. They contain no font data, only parameters learned from rendered page images.
  - Both fonts are credited in the model card and in the NOTICE:
    - Alef, by HaGilda & Mushon Zer-Aviv;
    - Gveret Levin, by The Gveret Levin Project Authors.
- **Item 4, licensor name: "HeOCR maintainers",** everywhere: the LICENSE copyright lines, the NOTICE and the model card.
- **Item 5, scope: R3h alone for the first release.**
  - R4d and A1 come later.
  - A1 first needs a proper `heocr_engine_training_run.v1` record (proposal §4).
  - Until they are released, decision 0008's licence and publication clauses still apply to R4d and A1.
- **Item 7, venues.**
  - Publish in as many venues as make sense, starting with both:
    - Zenodo, through `ketos publish`, with a version DOI;
    - Hugging Face Hub.
  - The maintainer explicitly accepts that a Zenodo deposit is permanent. He has no intention of deleting or changing deposits.
  - More venues may be added later.

## Still open

- **Item 6:** the model card text. The maintainer reads it himself; agents do not stand in for human reviewers.
- **Item 7, accounts:** which accounts or organisations to publish under on Zenodo and on Hugging Face.
- **Item 8:** each publishing action gets its own go-ahead from the maintainer, one by one:
  - a sandbox run;
  - the Zenodo deposit;
  - the Hugging Face upload;
  - any further venue.
- **The NOTICE text** (part of item 4) is drafted for the maintainer's review.

## Consequences

- **Nothing is published by this record.** Every training record keeps `published: false` until a deposit actually happens. No weights are committed to git.
- **Other models keep their records' terms.**
  - Other recognizers keep decision 0007's terms. `train-kraken` still writes `model_licence.status: "Needs verification"` for new runs.
  - R4d and A1 keep decision 0008's terms.
- **R3h's own training record** is updated separately, so that its `model_licence` points to this record. That change is proposed, not made here.
- **Before the first deposit,** proposal §4 still applies:
  - a sanitised training record to ship beside the weights;
  - one licensor name across all files;
  - citation by version DOI, never by concept DOI (decision 0006).
- **Later releases.** A release of R4d, A1 or a later recognizer gets its own record. That record can adopt this one's licence and venue terms.
