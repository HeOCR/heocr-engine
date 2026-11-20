# 0022 — htext ships one release per licence: a CC0 core, then CC BY and CC BY-SA supplements

- Status: accepted
- Date: 2026-11-18
- Decided by: the maintainer (Shay Palachy Affek), 2026-11-18, in the heocr-lead session; written by `lead[claude/claude-code#shay-macbook-m4]@heocr/opensource`
- Concerns: [HeOCR/htext](https://github.com/HeOCR/htext), the public-domain Hebrew text dataset

## Decision

1. **`htext-cc0`, the core.**
   - It holds only text that is in the public domain, dedicated under CC0, or not protected under §6 of the Israeli Copyright Act 2007 (legislation and official texts).
   - It can be used with no conditions. It is the default for training and for benchmarks.
2. **`htext-by`.**
   - It holds text under CC BY, or under other terms that require only attribution.
   - Each entry carries its credit line, and the release ships a consolidated NOTICE.
3. **`htext-by-sa`.**
   - It holds text under CC BY-SA, for example Hebrew Wikisource and the CC BY-SA versions on Sefaria.
   - The whole release is CC BY-SA 4.0, and each entry carries its credit line.
4. **What stays out.** Text under a non-commercial (NC) or no-derivatives (ND) licence is in no release.
5. **No mixing.** Every entry records its licence and its credit. A release contains only entries whose licence it allows, and a test enforces this.
6. **Models.** Models trained on the BY or BY-SA releases stay Apache-2.0 and credit those sources in their NOTICE. This follows the reasoning of decision 0016.

## Why

Users who want text with no obligations take the core alone. Users who can give credit gain more text, much of it carefully proofread, without anything in the core changing. Non-commercial and no-derivatives terms would contradict decision 0014: every model and dataset is released for any use.
