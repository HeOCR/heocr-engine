# 0006 — Kraken baseline models are user-supplied; licences recorded

- Status: accepted
- Date: 2026-11-01
- Decided by: R1c author; approach approved by the HeOCR team lead under delegation from the maintainer

## Evidence (Zenodo records API, read 2026-11-01)

| Model | Version DOI (pin this) | Concept DOI (do not pin) | Licence | File checksums |
|---|---|---|---|---|
| BiblIA_01 recognition, `BiblIA_01.mlmodel` ("Medieval Hebrew manuscripts version 1.0", Daniel Stökl Ben Ezra, 2021-09-06) | [10.5281/zenodo.5468286](https://doi.org/10.5281/zenodo.5468286) | 10.5281/zenodo.5468285 | CC-BY-SA-4.0 | md5 `f5674150b558844d690466cc5d7357c7` (Zenodo); sha256 `bb48c481d8c46b41465920482e253dc990163405c584d24700cfb0d9b4ca9147` (local copy, md5 matches) |
| kraken `blla` baseline segmentation, `blla.mlmodel` (Benjamin Kiessling, 2025-01-06) | [10.5281/zenodo.14602569](https://doi.org/10.5281/zenodo.14602569) | 10.5281/zenodo.14602568 | Apache-2.0 | md5 `0e3f0e1c5e954c8b673ef5dbd0865058` (Zenodo); sha256 `77a638a83c9e535620827a09e410ed36391e9e8e8126d5796a0f15b978186056` (local copy, md5 matches) |
| kraken `blla`, newer version (2026-09-21) | 10.5281/zenodo.22879549 | 10.5281/zenodo.14602568 | Apache-2.0 | Not used for the reference configuration |
| kraken engine 7.0.2 | PyPI package metadata | — | Apache-2.0 | Installed separately as the optional `kraken` extra |

The concept DOI 10.5281/zenodo.14602568, which HASH's `scripts/kraken_transcribe.py` cites, now resolves to the 2026 version. A concept DOI therefore does not identify a model.

## Decision

- No model is committed, bundled, redistributed or downloaded by heocr-engine. Users pass local model paths.
- Every prediction records each model's SHA-256 in `pipeline[].artifacts` under separate roles, `model:segmentation` and `model:recognition`. Runs are pinned by those hashes and by the version DOIs above, never by a concept DOI.
- Documentation that names BiblIA_01 attributes it as: "BiblIA_01, Medieval Hebrew manuscripts version 1.0, by Daniel Stökl Ben Ezra, licensed CC BY-SA 4.0, doi:10.5281/zenodo.5468286". Anyone who redistributes or adapts the weights must meet CC BY-SA 4.0 (attribution, ShareAlike). This repository does neither.
- **Needs verification:** whether CC BY-SA 4.0's ShareAlike condition reaches predictions (output text) made with BiblIA_01 is unresolved. This record draws no legal conclusion and makes no claim either way.
- Until that is settled, any prediction made with BiblIA_01 that HeOCR publishes or commits carries the attribution line above, and its licence is left to the maintainer's decision. Such predictions are identifiable by the recognition model's sha256 in `pipeline[].artifacts`.
- Kraken baseline results make no accuracy claim; on modern Hebrew cursive BiblIA_01 is expected to perform poorly.
