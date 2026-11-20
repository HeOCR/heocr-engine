# 0027 — Hold model and pipeline publication pending a state-of-the-art result

- Status: accepted
- Date: 2026-11-20
- Decided by: the maintainer
- Supersedes: the model publication instructions in [0010](0010-r3h-release.md), [0011](0011-first-release-adds-r4d-and-a1.md) and [0014](0014-open-release-always.md)

HeOCR is withdrawing the public releases of its trained models and packaged OCR pipelines. Keep weights and provenance in private archival storage. Code repositories and clean CC0 data remain public. Prior attribution and licence records remain part of the archive.

A new model or pipeline release requires a comparison against the state of the art on a registered real held-out set that demonstrates better results on at least one document type. Use evaluation's registered comparator and scoring rules. Keep model and pipeline work private at the artifact level until the maintainer approves a release under this criterion.

See the [current release documentation](../../release/README.md). The revised first-release card digests below pin the status and editorial update for review. Decision 0011 preserves the earlier card digests and the existing NOTICE digests.

| Card | SHA-256 |
| --- | --- |
| `release/r4d/card_body.md` | `3c893bd9c01b9008e24125d2672c5c50f430187d7a6a67612c14ba9b992fc654` |
| `release/a1/card_body.md` | `dab69e8327e5e1d8040ca01ef9b3736dd3d636364f8448ac237281ed5b199ccf` |
| `release/r3h/card_body.md` | `8be0382c6135a056581abb44998f46b83e5a497cc850e513f851610475330a0c` |
