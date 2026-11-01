# 0006 — Kraken baseline models are user-supplied; licences recorded

- Status: accepted
- Date: 2026-11-01
- Decided by: R1c author, under the team lead's instruction to verify BiblIA's licence before recommending it

## Evidence (Zenodo records API, read 2026-11-01)

| Model | Record | Licence | Notes |
|---|---|---|---|
| BiblIA_01 recognition (`BiblIA_01.mlmodel`, "Medieval Hebrew manuscripts version 1.0", Daniel Stökl Ben Ezra, 2021-09-06) | [10.5281/zenodo.5468286](https://doi.org/10.5281/zenodo.5468286) | CC-BY-SA-4.0 | Trained on medieval Ashkenazi, Italian and Sephardi bookhand, not modern cursive. |
| kraken `blla` baseline segmentation (Benjamin Kiessling) | concept [10.5281/zenodo.14602568](https://doi.org/10.5281/zenodo.14602568); versions 14602569 (2025-01-06) and 22879549 (2026-09-21) | Apache-2.0 | The concept DOI resolves to the newest version, so a DOI alone does not pin a model. |
| kraken engine 7.0.2 | PyPI package metadata | Apache-2.0 | Installed separately; not a dependency of this package. |

## Decision

- No model is committed, bundled or downloaded by heocr-engine. Users pass local model paths, and every prediction records each model's SHA-256 in `pipeline[].artifacts`. That hash, not a DOI, identifies the model used.
- The documentation names BiblIA_01 and `blla` as the reference configuration for the Kraken baseline and states their licences. Anyone redistributing BiblIA_01 must meet CC BY-SA 4.0 (attribution, ShareAlike). This repository does not redistribute it.
- Kraken baseline results make no accuracy claim; on modern Hebrew cursive BiblIA_01 is expected to perform poorly.
