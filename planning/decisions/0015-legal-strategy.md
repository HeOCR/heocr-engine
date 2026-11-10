# 0015 — Training inputs follow HeOCR's legal strategy for public-domain scans

- Status: accepted
- Date: 2026-11-10
- Decided by: the maintainer (Shay Palachy Affek), 2026-11-10; written by the HeOCR team lead
- Builds on: decision 0014

## Decision

The maintainer adopted HeOCR's legal strategy in full: "This is our legal strategy and outlook; I ascribe to it completely". The strategy is in hocrgen at `docs/legal/2026-11-10_legal_strategy.md`, and its operative rules are in `planning/decisions/2026-11-10-legal-strategy.md`. For models trained here:

- **Allowed inputs:** scans from NLI's "public domain, free use" class, and Google-digitized scans fetched from the Internet Archive or Wikimedia Commons.
- **Excluded inputs:** Google-digitized scans fetched from NLI ("public domain, non-commercial use"), unless NLI grants a written waiver.
- **Weights:** Apache-2.0, as in decision 0014. Each model's NOTICE lists its scan sources, the route each was fetched by, and the attribution each needs.
- **Training records:** each record names the data manifests it used. Those manifests carry the per-item provenance fields from hocrgen's record, so a model's inputs can be checked against the strategy, and rebuilt without any one item.
