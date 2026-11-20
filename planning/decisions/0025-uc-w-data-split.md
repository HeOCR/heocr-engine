# 0025 — Separate benchmarking, calibration and training for UC-W

- Status: accepted
- Date: 2026-11-20
- Decided by: the maintainer
- Amends: [0024 — Use-case benchmarks for modern printed Hebrew](0024-use-case-benchmarks-modern-print.md), for UC-W only

UC-W uses welfare inspection reports with structured references prepared by expert human analysts. Reserve about 10 matched reports for the benchmark, five for calibration, and the remaining matched reports for training. Assign whole facilities to a single split, using a seeded rule and stratifying by inspection year where feasible. Register the split before deriving labels, calibrating, training or scoring. Keep benchmark membership sealed.

The benchmark retains the restrictions and measures from 0024. The documents, expert references and raw outputs stay on the maintainer's machine. Publish aggregate scores only. Reserve the benchmark as a CLEAN target and exclude its facilities and content from training. Keep calibration separate from both training and benchmark scoring.

The training split may augment training with private components. Continue to release as much data as the applicable rights and privacy rules allow. The source workbooks and restricted derivatives stay local. This amendment does not change permissions to redistribute data, release rights, or the rules for UC-T.
