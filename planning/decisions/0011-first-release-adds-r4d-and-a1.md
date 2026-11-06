# 0011 — The first release adds R4d and A1 to R3h

- Status: accepted
- Date: 2026-11-06
- Decided by: the maintainer (Shay), 2026-11-06; written by R4b at the HeOCR team lead's request
- Supersedes:
  - decision 0010's scope (item 5, "R3h alone for the first release");
  - for the R4d segmenter and the A1 reading-order model, decision 0008's licence clause (`Needs verification`) and its "No publication" clause.

## Context

Decision 0010 scoped the first release to the R3h recognizer. Its card's end-to-end figures came from HeOCR's own pipeline: the R4d segmenter with the A1 reading order. Those two models were not part of that release.

So R3h was then scored with kraken's default `blla` segmentation, the pipeline a user of R3h alone would run:
- `segment -bl -d horizontal-rl`, then `ocr --reorder --base-dir R`, with kraken 7.0.2;
- through heocr-engine's CLI stage at `6f6df8b`;
- scored with hocrgen's `primary.v1` profile (`2d3efb0` for seed-101 and held-out, `c8fb74e` for the rest).

Every page was scored.

| Batch | R3h + `blla` CER | R3h + R4d + A1 CER |
|---|---|---|
| seed-101 | 0.168 | 0.020 |
| held-out | 0.238 | 0.010 |
| eval-mixed-heldout | 0.230 | 0.017 |
| eval-typo-heldout | 0.291 | 0.009 |
| eval-layout-heldout | 0.498 | 0.124 |
| hocrgen fixture (development set) | 0.404 | 0.130 |

The loss comes from `blla`'s segmentation and line order, not from the recognizer: R4a found the same for R3b with `blla`.

## Decision

- **Scope: R3h, R4d and A1** in the first release.
- **0010's other decisions apply to all three models:**
  - Apache-2.0 weights;
  - licensor "HeOCR maintainers";
  - the two OFL fonts credited, with OFL-1.1 not reaching the weights;
  - Zenodo with a version DOI, and Hugging Face Hub.

## Still open

As in decision 0010, now for all three models:
- the card text, which the maintainer reads himself (item 6);
- the Zenodo and Hugging Face accounts or organisations (item 7);
- a separate go-ahead for each publishing action (item 8).

## Consequences

- **Each model gets its own deposit:** card, front matter, NOTICE, LICENSE and sanitised training record. The cards link to each other as one pipeline.
- **A1 needs a proper record first.** It has no `heocr_engine_training_run.v1` record (proposal §4). One is written from the run's evidence before release, and fields the evidence cannot supply are marked as such.
- **A1's training pages** come from two hocrsyngen batches: R4d's (S10b text) and R3d's (S10b + S13a text). All of that text is CC0-1.0 (hocrsyngen ADR 0008).
- **Nothing is published by this record.** Every training record keeps `published: false` until a deposit actually happens.
- **Other models keep their records' terms.** Decision 0008 still applies to segmenters other than R4d and to reading-order models other than A1. Decision 0007 still applies to recognizers other than R3h.

## Note (2026-11-06): item 6 and the NOTICE text decided

On 2026-11-06 the maintainer approved the three model cards as they stand on main at `952e5b5`. This closes sign-off item 6. The approved files are:

| Card | sha256, with the production DOIs (plan step 2) |
|---|---|
| `release/r3h/card_body.md` | `da8b4e84920b8617bde6d1f6d74d89fde2334aca11d7f4156c6dba0769ddaa31` |
| `release/r4d/card_body.md` | `0b4c4313e86e261f7a4ab6209fe394d3d4bac7ec33f2477f4b7c880874080e9a` |
| `release/a1/card_body.md` | `6a03f50b204aec9d20ac84ee3e268225021ea2ae5322a0a0b7372ee41948dbfb` |

In a separate approval the same day, the maintainer approved the three NOTICE files. That decides item 4's NOTICE text. The approval came with one change, a grammar fix in R4d's NOTICE: it names one corpus, so "The corpus is dedicated" replaces "The corpora are dedicated". The approved files, after that fix, are:

| NOTICE | sha256 |
|---|---|
| `release/r3h/NOTICE` | `9711f741296fa7ee5cbf60900864c24b52b17884be3d4f8a579bc90790f14276` (unchanged from `952e5b5`) |
| `release/r4d/NOTICE` | `520faa889f2c9ca5f254168cea91ff017fa0f6dcc4c12054754cff8655266956` (with the fix) |
| `release/a1/NOTICE` | `c8b3ca662a59dfbc39a1df08a2f2589b174104ba9122fe0bb0f6822522349fae` (unchanged from `952e5b5`) |

- **The one planned change:** the reserved version DOIs go into each card's pipeline table and Citation section (`release/README.md`, plan step 2). Any other change to a card or a NOTICE needs the maintainer's review again.
- **2026-11-06, plan step 2, pending the maintainer's approval of the diff:** only the DOI lines changed, four per card:
  - three pipeline-table rows, each with that model's production version DOI and its `https://doi.org/` link;
  - the Citation line.

  The DOIs, reserved on zenodo.org, are R4d `10.5281/zenodo.24023070`, A1 `10.5281/zenodo.24023072` and R3h `10.5281/zenodo.24023074`. The approved cards at `952e5b5` had the sha256s r3h `8a068719…`, r4d `ff7d7a89…` and a1 `1b5d7439…`. The NOTICEs are unchanged.
- **Still open:** item 8, a separate go-ahead for each publishing action.

## Note (2026-11-06): item 7's accounts decided

The maintainer decided the publishing accounts on 2026-11-06:
- **Hugging Face:** a new HeOCR organisation, which he creates, with the repositories `HeOCR/heocr-r3h-recognition`, `HeOCR/heocr-r4d-segmentation` and `HeOCR/heocr-a1-reading-order`.
- **Zenodo:** deposits from his personal Zenodo account, into a new HeOCR community that he creates.
- **Zenodo creators:** Shay Palachy Affek, as a person (with his ORCID iD, if he has one), and "HeOCR maintainers", as an organisation.

How this is carried out, and the tokens he creates and keeps outside every repository, are in `release/README.md` ("Before step 1" and the plan for item 8). Item 8 stays open: each publishing action gets its own go-ahead.
