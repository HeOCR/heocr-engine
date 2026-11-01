# Agent instructions

## Scope
- Keep this file static and procedural. Roadmap status and decisions live in `planning/`.
- Treat merged `main` plus merged PR history as the source of truth for what is done.

## Setup and validation
- Install: `pip install .`
- Test: `python -m unittest discover -s tests`
- CI runs offline fixture tests only. Do not download models or call services in tests.

## Branching and commits
- Start from the latest `main`. Branch as `<tool>/<topic>` (for example `codex/…`, `claude/…`).
- Use Conventional Commits.

## Pull requests
- Open non-draft PRs with tests and an explanation of what changed, why, the impact, and the validation performed.
- Agent-authored PR bodies and comments begin with `Agent: <role>[<tool>#<host>] | Thread: <thread> @ heocr-engine`.
- Planned work uses the notation defined in `planning/README.md`. The PR title is `<notation>: <sentence-case summary>`, and the body has a top-level `## Planning notation` section naming the notation, its milestone, and the plan source document. If no notation exists yet, define it in `planning/` first.
- Label every PR (`kind:*`, `area:*`, `roadmap:*`) and assign it to its GitHub milestone.
- Do not merge your own PR. Every PR waits for green CI and maintainer review (`planning/decisions/0001-governance.md`).
- Before opening a PR, fetch and check open PRs and branches from other agents; stop and ask if the work would collide.

## Hard boundaries
- No network, paid-service, proprietary-model or LLM code in this repository. Their outputs may enter only as predictions through `validate-predictions` with `track: proprietary` (`planning/decisions/0005-proprietary-track.md`).
- Engines emit raw text. Do not normalize, reorder or "fix" predictions; scoring transforms belong to the evaluator (`planning/decisions/0002-normalization-boundary.md`).
- Keep source images, private text and predictions on sensitive material out of the repository.
- Prediction payloads must not contain local filesystem paths.
- Model weights are never committed or downloaded by this code. Users supply local model files, which are hashed.
