# R9 A/B clean rendered Knesset text: development disposition

The [registration](2026-11-13-r9-knesset-dose.md) fixed both arms, checkpoint selection and the development guards. The additional Knesset dose did not pass the guard rule, so it did not replace the comparison recipe.

## Runs

- **Training:** both arms ran as registered.
  - The start was R7 `lr1e4/heb_0.634_52608_117100` with the R8 starter.
  - The schedule was lr 1e-4 with reset, one epoch of the arm's own list, and 20-minute snapshots.
  - Both ran on the power scheduler, AC only.
- **Arm A** trained on `train_a.list`: 244,419 lines, sha256 `01778c76…aaf517320`. It finished at 2026-11-13 21:14, exit 0.
- **Arm B** trained on `train_b.list`: 304,419 lines, sha256 `7e6e0812…7bb6d`. It finished at 21:55, exit 0.
- **Clean check:** before launch, heocr-eval's official `check_train_overlap.py` reported CLEAN on both whole lists, holdout target included. The pins were checked again at launch.

## Evaluation and release

The checkpoint selection, guard books and auxiliary reports used development material. The registered mid-century test was not scored in this study. Candidate weights remain private. Public performance is reported on [registered real held-out benchmarks](https://heocr.org/en/benchmarks.html).
