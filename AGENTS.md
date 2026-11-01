# Agent instructions

Use Conventional Commits. Make changes in a feature branch and open a PR with tests and an explanation. Agent-authored PR bodies and comments begin with `Agent: <role>[<tool>#<host>] | Thread: <thread> @ heocr-engine`. Keep sensitive source images and predictions out of the repository. CI runs offline fixture tests; do not download models in tests. Do not add network or paid OCR calls to the engine without an explicit project decision.
