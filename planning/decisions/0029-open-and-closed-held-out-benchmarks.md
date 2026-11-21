# 0029 — Lead with open held-out benchmarks

- Status: proposed, pending maintainer approval
- Date: 2026-11-21
- Decision owner: the maintainer
- Amends: [0012](0012-real-page-scored-sets.md), [0017](0017-domain-separated-evaluation.md), [0023](0023-open-by-default.md), and [0024](0024-use-case-benchmarks-modern-print.md)
- Retains: [0027 release hold](0027-model-release-hold.md) and [0028 contamination policy](0028-contamination-policy-v2.md)

Each evaluation category gets two registered held-out sets of real documents: an **open** set and a **closed** set. The six categories are modern and old unpointed print, modern and old pointed print, and modern and old handwriting. The open set is the headline on the benchmark pages and in result summaries. The modern unpointed print category comes first. Each open set samples multiple independent sources and records its coverage limits.

## Open sets

Every released page or line carries separate, verified redistribution rights for its image, underlying text and reference transcription. The open route accepts public domain, CC0 or CC BY material, with the required credits and publication territories recorded for each asset. A public URL, apparently old work or accessible text layer establishes availability only. Verify the exact scan, edition and reference rights, as well as consent, personal data and capture metadata. Use physical captures of real documents. Register source and writer groups before any benchmark run and exclude those sources from all training and model selection under decision 0028.

Prepare a reviewable, versioned public dataset repository or archive, linked from the project benchmark page, with the exact scored image bytes, layout and reference files, per-asset licences and attribution, a SHA-256 manifest and stable IDs, split and assembly rules, and an immutable release tag or archive revision. The evaluation code, runner configuration, reader and checkpoint versions, normalisation, exclusions, and paired scoring and interval procedure are pinned to the release. Apply any authorized privacy sanitation before freezing the scored inputs. Corrections or changes in membership, rights, or denominator produce a new version with a changelog and independently labelled results. The maintainer approves publication through the project release process. Dataset and text-corpus publication each needs explicit approval for the exact release. Decision 0027 governs model, pipeline and app release timing.

## Closed sets

Use the closed set to cover settings and real documents whose images or references cannot be redistributed. Its dataset card and every table mark it **Closed · not independently reproducible**. Report it after the open results, with scope, coverage, counts, methods, uncertainty, source policy and the eligible comparator roster. Keep restricted inputs, references and per-item outputs private and disclose aggregates only. Preserve separate use-case measures and make the split between open and closed results visible in the site and release summaries.

## Launch and reporting

The launch criterion remains the currently registered rule until separately amended. Whether only OPEN sets can count toward launch is pending a maintainer decision. This proposal sets the reporting order and creates no launch result. Give every category an open headline or an explicit pending status, and disclose unresolved required comparators. Preserve prior scores on their original scope as supplemental evidence.

Apply decision 0028 to both cohorts. Keep source reservations and exact training provenance, tag allowed same-text exposure, and report the all-lines and non-overlap views with their denominators and any unavailable coverage. Use the same pinned scoring rules and eligible reader inputs within each comparison. The model, pipeline and app release hold remains in force until the launch criterion and maintainer approval are both satisfied.

— eval[openai/codex#shay-macbook-m4]@heocr/opensource
