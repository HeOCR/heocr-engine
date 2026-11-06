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
| `zenodo.yaml` | HTRMoPo v1 front matter. It validates against the HTRMoPo v1 schema once ketos fills `id` and `software_name` | front matter | — |
| `huggingface.yaml` | Hugging Face model-card metadata | — | `README.md` front matter |
| `NOTICE` | Attribution: kraken, the two OFL fonts, the CC0 AI-authored training text | see below | upload beside the weights |
| `LICENSE` | Apache License 2.0, unmodified | see below | upload beside the weights |

A card for either venue is its front matter between `---` lines, followed by `card_body.md`.

## What goes into each deposit

- **Zenodo, through `ketos publish -i <card> best_0.9959.safetensors`:**
  - ketos uploads the model file and a generated `metadata.json` only, so LICENSE, NOTICE and the training record would not travel with it.
  - The card body therefore states the licence and repeats the NOTICE credits.
  - If the deposit must carry the files themselves, `htrmopo publish` with a directory uploads every file in it. Its front matter would then need the `software_hints` that ketos otherwise computes.
  - That choice is open.
- **Hugging Face:**
  - `README.md` (`huggingface.yaml` front matter plus `card_body.md`);
  - `best_0.9959.safetensors`, `LICENSE`, `NOTICE`;
  - the sanitised training record.

## Before any deposit

- **The maintainer's review** of `card_body.md` and `NOTICE` (item 6).
- **The accounts** (item 7, still open).
- **A sanitised R3h training record** with `model_licence` pointing at decision 0010 (proposal §4).
- **The version DOI,** added to the card's Citation section after the deposit.
