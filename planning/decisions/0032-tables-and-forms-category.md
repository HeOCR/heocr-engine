# 0032 — Tables and forms as a launch category

- Status: accepted
- Date: 2026-11-25
- Decision owner: the maintainer
- Category: Shay, 2026-11-25 (tables and forms made a launch category)
- Amends: [0029](0029-open-and-closed-held-out-benchmarks.md) (adds a seventh category alongside the six text categories)
- Retains: [0027](0027-model-release-hold.md), [0028](0028-contamination-policy-v2.md), [0030](0030-efficiency-launch-path.md) and [0031](0031-llm-free-rivok-route.md)

## Decision

**Tables and forms** become a launch category, with two tasks:
1. **Table extraction:** an exact one-to-one reconstruction of each table, exportable to CSV and XLSX. That covers every cell's text, row and column spans, header rows and columns, and tables that continue across pages.
2. **Form structure:** the field labels, their values and the form's section hierarchy.

As in 0029, each task gets a registered real **OPEN** held-out set, which is the headline, and a **CLOSED** set. The closed set is a private real-world use-case collection, local only, with aggregates published. It is marked "Closed · not independently reproducible", and it is supplemental.

## References

- **Two independent annotations** per table or form, made image-first from the page, with adjudication of disagreements. This follows the reference protocol already used for the text sets.
- **Table references** are structured: cell grid, spans, header roles, reading direction (right-to-left, including mixed-direction cells), and cross-page continuation links.
- **Cell text** follows the same normalisation as the text categories.
- **Unresolvable cells** are masked for every reader alike and counted.
- **Annotator independence:** no reader whose output is scored may draft or decide a reference. Where an LLM assisted annotation, the LLM lanes of that family are diagnostic only.

## Metrics

| task | primary | secondary |
|---|---|---|
| tables | **table error = 1 − TEDS** (tree-edit-distance similarity on structure plus cell content), pooled over tables | GriTS (topology, content, location); exact-table match rate; cross-page stitch accuracy (the share of continued tables correctly joined); header-role accuracy; cell-text CER |
| forms | **field error = 1 − field/value F1** (a label–value pair matches when both sides match after normalisation) | section-tree similarity (tree edit distance over the section hierarchy); exact-form match rate; value-text CER |

The registered preregistration fixes exact definitions, matching thresholds and tie rules before any held-out pass.

## Comparators

- **Eligible:** open table and document-structure tools that run locally: Docling (TableFormer), Table Transformer, PP-Structure, Marker, MinerU, and Camelot or pdfplumber for born-digital PDFs where they apply. Each is pinned to an exact version and settings in the preregistration.
- **Costly upper bound:** hosted LLM and vision-language readers (Claude Haiku, Gemini), reported in a separate hosted stratum. They are not bars for the main test unless a pre-run amendment makes them one.

## Launch margin (proposed)

- **The test:** on the registered OPEN set, the one-sided 97.5% upper bound of the relative change in the task's primary error must be **below −3%** against **every** eligible local comparator. That is the same margin and paired cluster bootstrap (by document) as 0029.
- **Guards:**
  - **tables:** the exact-table match rate is not lower than the best comparator's;
  - **forms:** value-text CER is not worse than the best comparator's by more than 0.2 points.
- **Other routes:** the efficiency route (0030) and the LLM-free route (0031) apply to this category on the same terms.

## Data

- **DEV is disjoint from evaluation:** the development data of the tables track never shares a source document, issuer template or capture with the registered evaluation sets.
- **Sources and templates are reserved** before any training.
- **Born-digital and scanned or photographed tables** are separate strata, with no pooling unless registered.

Shay approved this decision on 2026-11-25 (relayed by the lead). His words, verbatim:

> I approve 0031 and 0032

— eval[claude/claude-code#shay-macbook-m4]@heocr/opensource
