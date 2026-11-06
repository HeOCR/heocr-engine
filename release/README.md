# First release: R4d + A1 + R3h (drafts)

**Status: drafts, for the maintainer's review. Nothing here is published.**
- The three cards are sign-off item 6 in [the release proposal](../planning/proposals/model-release.md) §7. The maintainer reads them himself.
- The accounts (item 7) and each publishing step (item 8) are still open.

The weights are not in this repository and never will be.

Terms:
- [decision 0010](../planning/decisions/0010-r3h-release.md): Apache-2.0, licensed by "HeOCR maintainers", with the fonts and kraken credited in each NOTICE, on Zenodo and Hugging Face;
- [decision 0011](../planning/decisions/0011-first-release-adds-r4d-and-a1.md): the scope, R3h + R4d + A1.

## The pipeline

| Step | Model | File | sha256 | Folder |
|---|---|---|---|---|
| Segmentation | R4d | `best_0.8618.safetensors` | `d32cd1a8efe7354445ccfea76551cc9943ca05792c332b5865f9bec985fe7bf7` | `r4d/` |
| Reading order | A1 | `best_0.0000.safetensors` | `69aa1946583bb68ddf13ef20860582f4aa982a46b2f79e38bd7d9ae20535fb56` | `a1/` |
| Recognition | R3h | `best_0.9959.safetensors` | `f76affa84e29536aa1d41f89d3507183c104f1620ca953fdfa5dd4b7a00ba6be` | `r3h/` |

Checked end to end on one seed-101 page on 2026-11-06, with kraken 7.0.2 on CPU, from a heocr-engine checkout (`pip install '.[kraken]'`):

```sh
heocr-engine kraken --api python \
  --segmentation-model best_0.8618.safetensors \
  --reading-order-model best_0.0000.safetensors --reading-order-classes region \
  --recognition-model best_0.9959.safetensors \
  page.jpg page.json
```

- The run took about 8 s.
- The prediction's `details` report `line_order: learned`, with 8 of 10 lines moved.
- Its text equals the scored R3h + R4d + A1 prediction for that page.

kraken 7.0.2 on its own cannot use A1, for two reasons:
- its neural reading order encodes the segmenter's line types (`default`, `stamp`), and A1 was trained on region types. After `ketos convert` of R4d + A1, `kraken segment` stops with "Reading order model class mapping … does not match segmentation model";
- its text output ignores a learned order ([mittagessen/kraken#820](https://github.com/mittagessen/kraken/issues/820)).

`kraken … segment -bl -d horizontal-rl -i best_0.8618.safetensors ocr -m best_0.9959.safetensors --reorder --base-dir R` runs, in kraken's heuristic order. It wrote its text, then aborted on exit with "recursive_mutex lock failed", which is the transient exit −6 seen in the scoring runs.

## Files in each folder

| File | What it is | Zenodo | Hugging Face |
|---|---|---|---|
| `card_body.md` | The model card text, shared by both venues | the card body | the `README.md` body |
| `zenodo.yaml` | HTRMoPo v1 front matter, with the `software_hints` that `ketos publish` would compute from the model and the pipeline CER (percent) in `metrics`. It validates against the HTRMoPo v1 schema once htrmopo fills `id` | front matter | — |
| `huggingface.yaml` | Hugging Face model-card metadata | — | `README.md` front matter |
| `NOTICE` | Attribution: kraken, the two OFL fonts, the CC0 AI-authored training text | in the deposit | beside the weights |
| `LICENSE` | Apache License 2.0, unmodified | in the deposit | beside the weights |
| `<model>_training_run.json` | The sanitised `heocr_engine_training_run.v1` record. It has no local paths, a `model_licence` pointing at decision 0010 (R3h) or 0011 (R4d, A1), and `published: false`. A1's is reconstructed from its run's evidence, and its `reconstruction` block lists what that evidence cannot supply | in the deposit | beside the weights |

A card for either venue is its front matter between `---` lines, followed by `card_body.md`.

## Deposits

**Zenodo: three records,** one per model, with `htrmopo publish` (team lead, 2026-11-06; decision 0010's note).
- `htrmopo publish -i <card> <deposit dir>` uploads every file at the top level of the deposit directory. It skips a top-level `README.md` and subdirectories.
- Each deposit directory holds only four files, and is assembled outside the repository, since the weights never enter git:
  - the weights;
  - `LICENSE`;
  - `NOTICE`;
  - the training record.
- htrmopo fills `id` with the pre-reserved DOI and keeps `metrics` and `software_hints` as written. `ketos publish` would replace both, and would upload only the weights and a generated `metadata.json`, so it is not used.
- htrmopo validates the front matter only after it has created the deposition, so validate it locally against the HTRMoPo v1 schema first.
- The cards' `The pipeline` tables get the three version DOIs once all three exist. That means a second version of the first records, or depositing all three before filling in the DOIs; the order is a publishing-step decision.

**Hugging Face: three repositories,** one per model, mirroring the Zenodo records. Each holds:
- `README.md` (`huggingface.yaml` front matter plus `card_body.md`);
- the weights, `LICENSE`, `NOTICE` and the training record.

The alternative is one repository with all three models and one card. It is simpler to download, but its card and versions would differ from Zenodo's three records.

## Before any deposit

- **The maintainer's review** of the three `card_body.md` and `NOTICE` files (item 6).
- **The accounts** (item 7).
- **Check the training records again** for local paths at deposit time (proposal §4).
- **Add the version DOIs** to each card's Citation section and pipeline table.
