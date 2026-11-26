# 0033 — Dual release: a MEASURED model and a FULL model

- Status: accepted
- Date: 2026-11-26
- Decided by: the maintainer (about 21:10, relayed by lead; recorded by eval)
- Operates under: [0027](0027-model-release-hold.md) (no release until a state-of-the-art result). This decision says *what* is released once 0027 allows it.

## Rule

Every released model ships as two variants built from **one identical recipe.** Users choose which to use.

1. **MEASURED:** trained on TRAIN, plus DEV after selection is done, which is always retrained into it. **This is the only variant scored on held-out sets.** Every reported, leaderboard or card number comes from it, under [0029](0029-open-and-closed-held-out-benchmarks.md) and contamination policy v2 amendment 1.
2. **FULL:** the same recipe, retrained on TRAIN + DEV + TEST.
   - It is **never scored** on the sets it was trained on. Its card carries the declaration: *"The MEASURED variant's held-out score is the expected, likely conservative, estimate for this model."*
   - **Sanity check:** one run on an external set that FULL never saw, to catch a broken run. Report it as a pass/fail sanity result, not as a benchmark claim.
   - Its **card lists every included set,** and FULL is **permanently ineligible** for those test sets.

## Rolling test sets

A category's test set is folded into FULL **only once a replacement test set for that category is registered,** so there is always at least one clean benchmark per category. The replaced set then retires from scoring for any model trained on it. The new set takes over as that category's held-out benchmark.

## Notes

- Selection never uses TEST. DEV is used for selection and only afterwards joins training, so MEASURED models are retrained on TRAIN + DEV with the selected recipe.
- Licences of folded-in sets apply. A non-commercial or eval-only set, for example BiblIA, is never folded into FULL.

