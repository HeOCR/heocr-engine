# R3h release files (draft)

**Status: draft, for the maintainer's review. Nothing here is published.**
- The model card text is sign-off item 6 in [the release proposal](../../planning/proposals/model-release.md) §7. The maintainer reads it himself.
- Each publishing step is item 8 and needs its own go-ahead.
- The publishing accounts are still open.

The weights are not in this repository and never will be.

Terms: [decision 0010](../../planning/decisions/0010-r3h-release.md). The weights are Apache-2.0, licensed by "HeOCR maintainers", with the fonts and kraken credited in the NOTICE.

## Files

| File | What it is | Zenodo | Hugging Face |
|---|---|---|---|
| `card_body.md` | The model card text, shared by both venues | the card body | the `README.md` body |
| `zenodo.yaml` | HTRMoPo v1 front matter for `htrmopo publish`, with the `software_hints` that `ketos publish` would compute and the CER figures in `metrics`. It validates against the HTRMoPo v1 schema once htrmopo fills `id` | front matter | — |
| `huggingface.yaml` | Hugging Face model-card metadata | — | `README.md` front matter |
| `NOTICE` | Attribution: kraken, the two OFL fonts, the CC0 AI-authored training text | in the deposit | beside the weights |
| `LICENSE` | Apache License 2.0, unmodified | in the deposit | beside the weights |
| `r3h_training_run.json` | The sanitised `heocr_engine_training_run.v1` record: no local paths, `model_licence` pointing at decision 0010, `published: false` | in the deposit | beside the weights |

A card for either venue is its front matter between `---` lines, followed by `card_body.md`.

## What goes into each deposit

- **Zenodo, with `htrmopo publish` (team lead, 2026-11-06; decision 0010's note):**
  - `htrmopo publish -i <card> <deposit dir>` uploads every file at the top level of the deposit directory. It skips a top-level `README.md` and subdirectories.
  - The deposit directory holds only:
    - `best_0.9959.safetensors`;
    - `LICENSE`;
    - `NOTICE`;
    - `r3h_training_run.json`.
  - It is assembled outside the repository, since the weights never enter git.
  - htrmopo fills `id` with the pre-reserved DOI, and keeps `metrics` and `software_hints` as written. `ketos publish` would replace both and would upload only the weights and a generated `metadata.json`, so it is not used.
  - htrmopo validates the front matter only after it has created the deposition. So validate it locally against the HTRMoPo v1 schema first.
- **Hugging Face:**
  - `README.md` (`huggingface.yaml` front matter plus `card_body.md`);
  - `best_0.9959.safetensors`, `LICENSE`, `NOTICE`, `r3h_training_run.json`.

## Before any deposit

- **The maintainer's review** of `card_body.md` and `NOTICE` (item 6).
- **The accounts** (item 7, still open).
- **The training record:** `r3h_training_run.json` is ready. Check it again for local paths at deposit time (proposal §4).
- **The version DOI,** added to the card's Citation section after the deposit.
