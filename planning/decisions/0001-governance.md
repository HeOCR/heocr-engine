# 0001 — Governance for heocr-engine

- Status: accepted
- Date: 2026-11-01
- Decided by: HeOCR team lead, under delegation from the maintainer (Shay Palachy Affek)

## Context

PR #1 merged about five minutes after it opened, with no milestone or planning notation. hocrgen already uses planning notation, labels, milestones and a `## Planning notation` PR section (`hocrgen/AGENTS.md`).

## Decision

heocr-engine adopts hocrgen-style governance: the notation in `planning/README.md`, `kind:*`/`area:*`/`roadmap:*` labels, a GitHub milestone per roadmap milestone, and a `## Planning notation` section in planned PRs. Authors do not merge their own PRs; every PR waits for green CI and maintainer review.

## Consequences

`AGENTS.md` carries these rules. PR #1 stays as merged; its Tesseract baseline is recorded as pre-R1 work.
