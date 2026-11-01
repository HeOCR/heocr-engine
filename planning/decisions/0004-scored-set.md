# 0004 — What counts as the scored set for now

- Status: accepted
- Date: 2026-11-01
- Decided by: HeOCR team lead, under delegation from the maintainer

## Context

There will be no new human transcription campaign (hocrgen issue #86). No current HASH transcript meets hocrgen's human-reviewed bar, and the tender-page transcriptions are unadjudicated candidates with unresolved rights.

## Decision

Synthetic gold (governed hocrsyngen batches with known text) is the reported number. HASH and tender pages are scored only as `unreviewed` diagnostics. Agent or GPT-4o review is never labelled "reviewed" or "human".

## Consequences for this repository

Documentation and reports produced here must not describe a score on real pages as a benchmark result, and must name the reference status they used.
