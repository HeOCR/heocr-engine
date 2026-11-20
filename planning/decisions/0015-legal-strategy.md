# 0015 — Training inputs follow HeOCR's legal strategy for public-domain scans

- Status: accepted
- Date: 2026-11-10
- Decided by: the maintainer (Shay Palachy Affek), 2026-11-10; written by the HeOCR team lead
- Builds on: decision 0014

## Decision

The maintainer adopted HeOCR's legal strategy in full: "This is our legal strategy and outlook; I ascribe to it completely". The strategy is in hocrgen at `docs/legal/2026-11-10_legal_strategy.md`, and its operative rules are in `planning/decisions/2026-11-10-legal-strategy.md`. For models trained here:

- **Scan sources allowed:**
  - NLI "public domain, free use" scans;
  - non-Google library scans from the Internet Archive (hocrgen decision 2026-11-09);
  - Google-digitized scans fetched from the Internet Archive or Wikimedia Commons (Routes B and C).

  NLI-origin scans fetched from the Internet Archive or Wikimedia Commons are accepted too, under the maintainer's ruling of 2026-11-10 ("Yes, same logic") in the hocrgen record. Their NLI origin is recorded and credited. Other inputs, such as texts, fonts and banks, follow decision 0014 item 2.
- **Excluded:** Google-digitized scans fetched from NLI ("public domain, non-commercial use", Route A), unless NLI grants a written waiver.
- **Weights:** Apache-2.0, as in decision 0010 item 2 (R3h), decision 0011 (R4d and A1) and the strategy's item 6. Each model's NOTICE lists its scan sources, the route each was fetched by, and the attribution each needs.
- **Training records:** each record names the data manifests it used. Those manifests carry the per-item provenance fields from hocrgen's record, so a model's inputs can be checked against the strategy, and rebuilt without any one item.
