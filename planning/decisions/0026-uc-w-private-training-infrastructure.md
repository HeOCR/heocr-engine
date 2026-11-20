# 0026 — Private processing and storage for UC-W training

- Status: accepted
- Date: 2026-11-20
- Decided by: the maintainer
- Amends: [0025 — Separate benchmarking, calibration and training for UC-W](0025-uc-w-data-split.md)

The registered UC-W training split and its derived labels may be processed on the project's private RunPod pods and stored in private Hugging Face datasets under the HeOCR organization. Keep the documents, labels, artifacts containing them, and access to those datasets private. Prepare training-only inputs locally before transfer. The original workbooks from expert human analysts contain material across the split and stay local.

The benchmark and calibration splits, their membership, and their source and derived material stay sealed on the maintainer's machine. The benchmark remains a local CLEAN target and retains the aggregate reporting rules in 0024. The training exception grants no public release permission and does not change the rules for UC-T.
