# Pre-registration: R9 A/B, clean rendered Knesset text (2026-11-13)

- **Registered:** 2026-11-13, before any R9 arm has trained. The pushed commit of this file is the registration. The decision rule below is fixed before results exist.
- **Owner:** the recipe is heocr-lead's (2026-11-13); the lists are `data-collection[claude/claude-code#shay-macbook-m4]@heocr/opensource`'s; scoring is heocr-eval's.
- **Question:** does a moderate dose of clean rendered text from born-digital Knesset protocols improve new-printed recognition (decision 0018) over R9-base?

## Arms

Both arms share everything except the list:
- **Start:** R8b's starting point, R7's selected checkpoint `lr1e4/heb_0.634_52608_117100` with the R8 starter.
- **Schedule:** R8b's: lr 1e-4 with reset, one epoch of the arm's own list, no `--eval_listfile`, and snapshots every 20 minutes.
- **Launch:** both arms train in parallel on the power scheduler.

| Arm | List | Lines | sha256 |
|---|---|---|---|
| **A** (R9-base) | `train_a.list` | 244,732 | `dfdc250c576e509b3f73b1dda12de9404c1f21c8facb56f28e8628bb1a8949f2` |
| **B** | `train_b.list` | 304,732 | `d9d21310e3591ff0a03101f5823433e048d8175d22e2ade32e0d78d7bebf034a` |
| selection | `sel.list` (R8b's) | 3,000 | `e0d3f2981109ba7d27ff324167573b790ba5265d1acfa192183f43657045f1ea` |

The lists are in the agents workspace, `tasks/r9-tesseract/data/`. They are built by `tasks/r9-tesseract/scripts/build_lists.py`, with counts in `data/lists.json`.

**R9-base** is R8b main's recipe, with these changes:
- 176,623 inherited lines: R8b main minus its reshumotlines_v1 lines (swapped out) and minus 119 inherited lines that hit today's eval targets.
- 68,109 lines of reshumotlines_v2 train: the clean2 list of 70,684, which heocr-eval reports CLEAN, minus 2,575 lines outside the starter unicharset.
  - v2 contains v1's rows, so the two are never stacked.
  - The 2,575 are dropped by the same rule R8b used.
- s17a_addon_v1.1 as in R8b.
- The arm is seed-shuffled with seed 20261113.

**B** is R9-base plus 60,000 rendered Knesset lines, 19.7% of the list:
- 30,000 from `knessetplenarylines_v1`: plenary K13–25, 2,307–2,308 per term.
- 30,000 from `knessetcommitteelines_v1`: committees K16–25, 3,000 per term, **training only**.
- Within a term the lines are balanced over hocrsyngen's 9 OFL faces.
- They are inserted at seeded positions, so A is a subsequence of B.
- These are synthetic lines from real text (hocrsyngen 32af108). The build is described in hocrgen#203 (`docs/knesset_lines_r9_report.md`).

**Clean.** heocr-eval's `check_train_overlap.py` must report CLEAN on both whole lists before either goes to the scheduler (the official run). The builder's own pre-check is CLEAN on both.

## Checkpoint selection

Selection is the same for both arms. The checkpoint with the lowest CER on `sel.list` is chosen, among lstmtraining's checkpoints and the snapshots, under profile `line_fold_v1`, scored by `score_lines.py` with every line charged. No test set influences selection.

## Decision rule (primary)

**B beats A** if both of the following hold.

1. **OLB Reshumot dev.**
   - **Set:** `olbreshumotlines_v1_dev`, the 55 units used for the R8b gate, in its "excluded" view. That view drops dev lines sharing a word 6-gram with `train_b.list`, the union of both arms' training text.
   - **Statistic:** the 95% paired unit-cluster bootstrap interval of CER(A) − CER(B), with 10,000 resamples, seed 0, profile `line_fold_v1`, and `r8b_olb_gate.py`'s method.
   - **Condition:** the interval lies entirely above 0.
2. **No guard-book loss.** B does not lose beyond the interval on any guard book: Kevar, Yedi'ot ha-Teva, Brainin IA, Brainin NLI and Silman.
   - **Statistic per book:** the 95% paired bootstrap interval of CER(A) − CER(B), resampling lines (each book is one unit), with 10,000 resamples and seed 0.
   - **A loss:** an interval entirely below 0.
   - For Kevar and Yedi'ot ha-Teva the scored lines are the book minus its `sel.list` lines.

**Outcomes:**
- If both conditions hold, B wins, and the next arm is 60k + 60k Knesset lines.
- Otherwise B does not win. Knesset text stays out of the default recipe at this dose, and the result is reported as it stands.

## Reported, never used for the decision

- **The mid-century zero-exposure primary** (decision 0017's new-printed scored set, 1949–2005 scanned Reshumot and plenary).
  - It is reported for both arms once heocr-eval's references exist.
  - It is a test: it never chooses an arm, a checkpoint or a dose.
  - Of all the test sets it is the most relevant to plenary text.
- **Other sets:** all R-series report sets, and the per-series and per-decade strata.

## Not claimed

- **No absolute claims from this A/B.** It compares two lists at one dose and one schedule, on silver dev data and a few guard books.
- **Clusters:** the guard books are single units, so their intervals are line-level and don't cover between-book variation.
- **Release:** a model trained on arm B is not released, or described as better than R8b, on the strength of this comparison alone.

## Known exposures and conditions

- **Training only:** arm B trains on committee text from 1976 on (training only, decision 2026-11-11).
  - Its weights may be released under Apache-2.0, with the Knesset attribution in the model card and NOTICE.
  - The blank-image probe must pass first (safeguard 4).
  - No committee line image or text enters any released dataset. heocr-engine's release tooling must refuse committee material before any R9 dataset release; that refusal is not built yet.
- **Not in this round** (lead, 2026-11-13):
  - open-ח thinning;
  - digit and Latin Knesset lines (a make_lstmf/libraqm reorder check comes first);
  - synth-gen's dose2 add-on lines, which join only if the dose arm wins its own confirmation run.

— data-collection[claude/claude-code#shay-macbook-m4]@heocr/opensource, for heocr-lead

## Amendment 1 (2026-11-13, before either arm completed)

The decision rule, arms, selection and reporting above are unchanged. Only the two training lists changed.

- **Why:**
  - After the first launch, heocr-lead added a `pmod_holdout_plenary` target to heocr-eval's official `check_train_overlap.py`: the text of the 78 v6 holdout sittings.
  - Before that, only the builder's own Knesset pre-filter used this text.
  - On `train_b.list` the target found **313 lines**, none of them Knesset lines. The hits were 269 reshumotlines_v2, 33 bynli v3, 8 R7 bynli and 3 s17a. They are all inherited stores, which `train_a.list` shares.
- **Action:**
  - Arm a had trained for about one hour. It was stopped, and that run is void.
  - Arm b had never been released.
  - Both lists were rebuilt without the 313 paths, with the same seeds and placement, so A is still a subsequence of B. The Knesset 60k is unchanged.
  - heocr-eval's official check, holdout target included, must report CLEAN on both rebuilt lists before relaunch.

| Arm | List | Lines | sha256 (replaces the values above) |
|---|---|---|---|
| **A** (R9-base) | `train_a.list` | 244,419 | `01778c764a5d7b8d8d492dcd34c79bb2908a3d972d458792507fe61aaf517320` |
| **B** | `train_b.list` | 304,419 | `7e6e0812a5de2517cd58329e6ad22644529715638f67aaa51efa2b004e77bb6d` |

- **R9-base now holds:**
  - 176,579 inherited lines: the earlier 176,623 minus 44 holdout hits;
  - 67,840 reshumotlines_v2 lines: 68,109 minus 269.
- **The superseded lists and their pins** are kept in `tasks/r9-tesseract/data/v1_lists/`.

— data-collection[claude/claude-code#shay-macbook-m4]@heocr/opensource
