# Results: R9 A/B, clean rendered Knesset text (2026-11-14)

This reports the outcome of the R9 pre-registration ([2026-11-13-r9-knesset-dose.md](2026-11-13-r9-knesset-dose.md), #80, with amendment 1, #82). The decision rule, the arms, the lists and the selection were all fixed there before training. This file changes none of them.

**Outcome: B does not win.** Knesset text stays out of the default recipe at this dose, as registered.
- **Condition 1 holds.** On OLB Reshumot dev, B beats A with an interval entirely above 0.
- **Condition 2 fails.** B loses on two of the five guard books, Brainin NLI and Silman.

## Runs

- **Training:** both arms ran as registered.
  - The start was R7 `lr1e4/heb_0.634_52608_117100` with the R8 starter.
  - The schedule was lr 1e-4 with reset, one epoch of the arm's own list, and 20-minute snapshots.
  - Both ran on the power scheduler, AC only.
- **Arm A** trained on `train_a.list`: 244,419 lines, sha256 `01778c76…aaf517320`. It finished at 2026-11-13 21:14, exit 0.
- **Arm B** trained on `train_b.list`: 304,419 lines, sha256 `7e6e0812…7bb6d`. It finished at 21:55, exit 0.
- **Clean check:** before launch, heocr-eval's official `check_train_overlap.py` reported CLEAN on both whole lists, holdout target included. The pins were checked again at launch.

## Checkpoint selection

Selection was run as registered:
- **Candidates:** every lstmtraining checkpoint and snapshot of each arm, 36 for A and 34 for B.
- **Scoring:** each candidate decoded `sel.list` (R8b's 3,000 lines, sha256 `e0d3f298…`). `score_lines.py` scored it under `line_fold_v1`, with every line charged.
- **Rule:** the lowest CER wins. There was no tie at the best.
- **Packing:** the chosen checkpoint was packed with `lstmtraining --stop_training` and the R8b starter. The packed model re-scores identically on `sel.list`.

| Arm | Pick | sel CER | sel WER | Packed `heb.traineddata` sha256 |
|---|---|---|---|---|
| A | `heb_snap_194903` | 0.876 | 3.978 | `9ad5ef42a9e62f7ffb1fa7f49f69e422b547730606064862e04b57e0951d7050` |
| B | `heb_snap_204405` | 0.869 | 3.957 | `84056a3ee6d6376db7b7d6e666810ad32f99dc5466eb8e093d112c6068abc08e` |

For scale, R8b main-fold's pick scores 0.873 on the same list. Selection CER is not a result.

## Decision rule

The figures are from heocr-eval's `r9_gate.py`, output `r9_gate_v1.json` (sha256 `ad2f6e71e00b44cb16204b15c2d343653273e7fd65fae6f5d4c74bf91114420e`), in the agents workspace under `tasks/eval-domains/`.
- **Method:** profile `line_fold_v1`, every line charged, 10,000 resamples, seed 0.
- **Pins:** the script stops if any pin differs: the models, the lists, and stock tessdata_best `heb` at `e12c65a`.
- **Cross-check:** it also stops if the R8b, R7 or stock figures differ from the published R8b report-set figures. They match.

**Stock Tesseract** (tessdata_best `heb` at `e12c65a`, the base model) is shown on every set. It is decoded exactly as our models are: the same psm 13 line files and the same profile. It is a reference reader, not a decision arm.

### 1. OLB Reshumot dev: holds

The set is `olbreshumotlines_v1_dev`: 55 units and 3,254 lines, with intervals from a paired unit-cluster bootstrap.
- **The "excluded" view equals "all":** no dev line shares a word 6-gram with `train_b.list`.
- **Why R8b's exposure is gone:** R8b's 11 exposed OLB lines all came through reshumotlines_v1, which R9 swapped out. Both R9 lists also passed the official check against the OLB dev target.

| View | Lines | **A** | **B** | R8b | R7 | stock | A − B [95%] |
|---|---|---|---|---|---|---|---|
| excluded (= all) | 3,254 | 2.124 | 2.033 | 2.129 | 2.934 | 5.428 | **+0.091 [+0.031, +0.129]** |
| exact † | 2,028 | 0.703 | 0.606 | 0.735 | 1.320 | 3.965 | +0.097 [+0.058, +0.144] |
| not exact | 1,226 | 4.054 | 3.970 | 4.021 | 5.125 | 7.415 | +0.084 [−0.055, +0.146] |
| at most 60 lines per unit | 1,484 | 1.469 | 1.387 | 1.473 | 2.271 | 4.987 | +0.082 [+0.030, +0.138] |

All figures are CER %. Only the first row's A − B interval decides.

- † **The "exact" lines** are lines that the fast stock `heb` model read exactly as the label, so the tier favours stock by construction.
- **Against R8b** (reported, not a decision):
  - B − R8b = −0.096 [−0.137, −0.039].
  - A − R8b = −0.005 [−0.046, +0.021].

### 2. Guard books: fails

The figure is CER(A) − CER(B). Each book is one unit, so lines are resampled. A loss is an interval entirely below 0.

| Guard book | Lines | A | B | R8b | R7 | stock | A − B [95%] | Result |
|---|---|---|---|---|---|---|---|---|
| Kevar (book minus its sel lines) | 4,600 | 0.761 | 0.748 | 0.757 | 0.848 | 5.664 | +0.013 [−0.003, +0.030] | ok |
| Yedi'ot ha-Teva (book minus its sel lines) | 4,600 | 1.001 | 0.994 | 1.019 | 1.336 | 9.168 | +0.007 [−0.009, +0.023] | ok |
| Brainin IA | 6,257 | 0.736 | 0.727 | 0.743 | 0.635 | 5.071 | +0.009 [−0.006, +0.023] | ok |
| **Brainin NLI** | 4,046 | 1.053 | 1.088 | 1.073 | 1.355 | 10.450 | **−0.035 [−0.059, −0.010]** | **loss** |
| **Silman** | 3,046 | 0.835 | 0.892 | 0.869 | 1.001 | 5.824 | **−0.057 [−0.079, −0.034]** | **loss** |

**Verdict:** `B_beats_A = false`. Following the registered outcome, the next arm (60k + 60k Knesset lines) does not run. Knesset text is not added to the default recipe at this dose.

## Reported, never used for the decision

### Report sets

These are the R8b card's report sets, with CER % on all lines.
- The A − B column is paired: a unit-cluster bootstrap where a set has several units, otherwise lines are resampled.
- "Exposed" counts lines sharing a word 6-gram with the exposure pool: R8b main, R7, s17a-addon and `train_b.list`. The JSON also holds each set's view without exposed lines.

| Set | Lines | Exposed | **A** | **B** | R8b | R7 | stock | A − B [95%] |
|---|---|---|---|---|---|---|---|---|
| Silman | 3,046 | 0 | 0.835 | 0.892 | 0.869 | 1.001 | 5.824 | −0.057 [−0.079, −0.034] |
| Brainin NLI | 4,046 | 0 | 1.053 | 1.088 | 1.073 | 1.355 | 10.450 | −0.035 [−0.059, −0.010] |
| Brainin IA (bynli v3 dev) | 6,257 | 62 | 0.736 | 0.727 | 0.743 | 0.635 | 5.071 | +0.009 [−0.006, +0.023] |
| Reshumot dev (rendered) | 2,716 | 29 | 0.957 | 1.078 | 1.179 | 7.789 | 6.613 | −0.121 [−0.221, −0.041] |
| rab dev (Mekhilta, old printed) | 3,141 | 63 | 1.061 | 1.087 | 1.056 | 1.896 | 7.512 | −0.026 [−0.043, −0.008] |
| ws dev | 257 | 0 | 7.175 | 7.149 | 6.932 | 8.030 | 14.672 | +0.026 [−0.111, +0.164] |
| Bodek | 21 | 0 | 4.692 | 4.290 | 5.094 | 6.166 | 15.684 | +0.402 [−0.137, +0.990] |
| Kevar held-out | 4,600 | 11 | 0.761 | 0.748 | 0.757 | 0.848 | 5.664 | +0.013 [−0.003, +0.030] |
| Yedi'ot ha-Teva held-out | 4,600 | 8 | 1.001 | 0.994 | 1.019 | 1.336 | 9.168 | +0.007 [−0.009, +0.023] |

**Observations.** These are paired intervals from the same JSON, none of them decisions.
- **B's gains are on modern, Reshumot-like print.** It is ahead on OLB dev, by 0.091 over A and 0.096 over R8b.
- **B's losses are on mid-century books.** It is behind A on Silman, Brainin NLI, Reshumot dev (rendered) and rab dev.
- **A is the strongest arm on three sets.**
  - Against R8b: Reshumot dev −0.222 [−0.325, −0.151] and Silman −0.034 [−0.054, −0.012].
  - It ties R8b elsewhere, except ws dev, where it is worse: +0.243 [+0.130, +0.362].
- **R7 still leads on Brainin IA.**
- **Stock is far behind every trained model on every set.**

### Mid-century zero-exposure primary: not scored yet

heocr-eval's references for decision 0017's new-printed scored set do not exist yet: no review export has landed. R9a and R9b will be added as reported readers when they do. That set is a test and never chooses an arm, a checkpoint or a dose.

## Not claimed

- **This compares two lists at one dose and one schedule**, on silver dev data and five guard books. It does not show that Knesset text cannot help at another dose, mix or schedule.
- **The guard books are single units.** Their intervals are line-level and do not cover between-book variation.
- **Neither model is released or described as better than R8b** on the strength of this comparison. A beating R8b on two report sets is a report-set observation, not a release decision.

## Release preconditions (unchanged)

- **No R9 dataset release** until heocr-engine's release tooling refuses committee material. That refusal is still not built.
- **No committee line image or text** enters any released dataset. `knessetcommitteelines_v1` is training only. hocrgen's own export refuses it (hocrgen#203), but heocr-engine's release tooling does not yet.
- **If arm B's weights are ever released:** the blank-image probe (safeguard 4) must pass first, and the Knesset attribution goes into the card and NOTICE.

## Files (agents workspace, `tasks/`)

- **Selection:** `r9-tesseract/scripts/select.sh`. The full ranking is in `r9-tesseract/runs/selection_line_fold_v1.json`, and the picks with their shas are in `runs/selected.txt` and `runs/model.sha256`.
- **Models:** `r9-tesseract/models/{a,b}/heb.traineddata`.
- **Gate:** `eval-domains/scripts/r9_gate.py`, with its output in `eval-domains/outputs/r9_gate_v1.json`. The decodes are in `eval-domains/intermediates/score_lines/<set>/out/r9{a,b}.txt`.

— data-collection[claude/claude-code#shay-macbook-m4]@heocr/opensource; scoring by eval[claude/claude-code#shay-macbook-m4]@heocr/opensource
