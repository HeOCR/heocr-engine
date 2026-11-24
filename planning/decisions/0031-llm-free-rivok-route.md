# 0031 — Add an LLM-free route against Rivok

- Status: accepted
- Date: 2026-11-25
- Decision owner: the maintainer
- Goal: Shay, 2026-11-25, goal (c)
- Amends: [0029](0029-open-and-closed-held-out-benchmarks.md) (adds a route; the 0029 and 0030 routes continue)
- Retains: [0027 release hold](0027-model-release-hold.md), [0028 contamination policy](0028-contamination-policy-v2.md) and [0030 efficiency route](0030-efficiency-launch-path.md)

## Decision

HeOCR may qualify for launch when an **LLM-free** HeOCR reader beats **Rivok** by **at least 2% relative CER** on one registered text type or task, and runs **at most 30% slower** than Rivok on the same hardware.

- **LLM-free:** no large language model or hosted vision-language model at inference, in any stage of the qualifying configuration.
- **Per-case specialists are allowed:** a model trained or tuned for one text type, carrier or task. Each candidate and its stratum are registered before that stratum's held-out pass. A candidate is never chosen after seeing held-out scores.

## Evaluation

- **Sets:** only registered real **OPEN** held-out sets count, as in 0029. A CLOSED result is reported after the open results and is supplemental.
- **Statistical test:** the 0029 paired procedure on the registered primary CER.
  - Resample registered source clusters in pairs (2,000 replicates, seed 0), keeping sister pages and captures together.
  - Against **every Rivok lane** eligible in that stratum (Tesseract Full, Tesseract Lite, Paddle), the one-sided 97.5% upper bound of `(CER(HeOCR) − CER(Rivok)) / CER(Rivok)` must be **below −2%**.
  - When a Rivok lane's CER is below 2%, at least 0.2 points of absolute improvement are also required.
  - Familywise control is pre-registered if more than one stratum can qualify in one pass.
- **Speed:** the median model-only seconds per line on a registered DEV timing panel must be **at most 1.30×** the Rivok lane's.
  - Both arms run on the same frozen hardware, threads and runtime.
  - At least three isolated, order-rotated repeats are required.
  - End-to-end pipeline time and peak memory are reported as context.
  - The speed gate applies to the same configuration that passes the accuracy test.
- **Exposure:** decision 0028 applies, and both the all and non-overlap views are reported. Rivok's training exposure is recorded as unknown where it can't be established.

## Reporting

A qualifying claim names the text type or task, the carrier scope, the Rivok lanes beaten, the speed ratio and the hardware. It does not generalise beyond the registered stratum. A missing required Rivok lane leaves the stratum pending.

**First target:** a phone-capture specialist for modern unpointed print, on a larger registered phone-capture stratum than the current open set provides.

Shay approved this decision on 2026-11-25 (relayed by the lead). His words, verbatim:

> I approve 0031 and 0032

— eval[claude/claude-code#shay-macbook-m4]@heocr/opensource
