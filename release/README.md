# First release: R4d + A1 + R3h (drafts)

**Status: not published. The maintainer approved the three cards on 2026-11-06.**
- That approval closes sign-off item 6 in [the release proposal](../planning/proposals/model-release.md) §7, for the cards as they stand at `952e5b5` (decision 0011's note).
- The accounts (item 7) and each publishing step (item 8) are still open.

The weights are not in this repository and never will be.

Terms:
- [decision 0010](../planning/decisions/0010-r3h-release.md): Apache-2.0, licensed by "HeOCR maintainers", with the fonts and kraken credited in each NOTICE, on Zenodo and Hugging Face;
- [decision 0011](../planning/decisions/0011-first-release-adds-r4d-and-a1.md): the scope, R3h + R4d + A1.

## The pipeline

| Step | Model | Release file | Trained as | sha256 | Folder |
|---|---|---|---|---|---|
| Segmentation | R4d | `heocr-r4d-segmentation.safetensors` | `best_0.8618.safetensors` | `d32cd1a8efe7354445ccfea76551cc9943ca05792c332b5865f9bec985fe7bf7` | `r4d/` |
| Reading order | A1 | `heocr-a1-reading-order.safetensors` | `best_0.0000.safetensors` | `69aa1946583bb68ddf13ef20860582f4aa982a46b2f79e38bd7d9ae20535fb56` | `a1/` |
| Recognition | R3h | `heocr-r3h-recognition.safetensors` | `best_0.9959.safetensors` | `f76affa84e29536aa1d41f89d3507183c104f1620ca953fdfa5dd4b7a00ba6be` | `r3h/` |

Checked end to end on one seed-101 page on 2026-11-06, with kraken 7.0.2 on CPU, from a heocr-engine checkout (`pip install '.[kraken]'`). The files were checked under other names; the bytes are identical:

```sh
heocr-engine kraken --api python \
  --segmentation-model heocr-r4d-segmentation.safetensors \
  --reading-order-model heocr-a1-reading-order.safetensors --reading-order-classes region \
  --recognition-model heocr-r3h-recognition.safetensors \
  page.jpg page.json
```

- The run took about 8 s.
- The prediction's `details` report `line_order: learned`, with 8 of 10 lines moved.
- Its text equals the scored R3h + R4d + A1 prediction for that page.

kraken 7.0.2 on its own cannot use A1, for two reasons:
- its neural reading order encodes the segmenter's line types (`default`, `stamp`), and A1 was trained on region types. After `ketos convert` of R4d + A1, `kraken segment` stops with "Reading order model class mapping … does not match segmentation model";
- its text output ignores a learned order ([mittagessen/kraken#820](https://github.com/mittagessen/kraken/issues/820)).

`kraken … segment -bl -d horizontal-rl -i heocr-r4d-segmentation.safetensors ocr -m heocr-r3h-recognition.safetensors --reorder --base-dir R` runs, in kraken's heuristic order. It wrote its text, then aborted on exit with "recursive_mutex lock failed", which is the transient exit −6 seen in the scoring runs.

The release names are descriptive. `best_0.0000.safetensors` would read as zero accuracy, although 0.0000 is A1's validation distance, where 0 is best. Renaming leaves the bytes and sha256 unchanged. Each card and each record (`output.release_file_name`, beside `output.file_name`) names both files.

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

**Zenodo: three records,** one per model, in htrmopo's deposit format. The team lead chose htrmopo's route on 2026-11-06 (decision 0010's note). Because the DOIs are reserved first, the deposit runs htrmopo's steps against a reserved draft; see the plan below.
- **Contents:** each record holds the card as `README.md`, plus four files:
  - the weights, under their release name;
  - `LICENSE`;
  - `NOTICE`;
  - the training record.
- **Assembly:** the deposit directory is assembled outside the repository, since the weights never enter git.
- **Front matter:** it keeps `metrics` and `software_hints` as written. `ketos publish` would replace both, and would upload only the weights and a generated `metadata.json`, so it is not used.
- **Validation:** validate each card locally against the HTRMoPo v1 schema before any upload. htrmopo itself validates only after it has created a deposition.

**Hugging Face: three repositories,** one per model, mirroring the Zenodo records. Each holds:
- `README.md` (`huggingface.yaml` front matter plus `card_body.md`);
- the weights, `LICENSE`, `NOTICE` and the training record.

The alternative is one repository with all three models and one card. It is simpler to download, but its card and versions would differ from Zenodo's three records.

## Plan for item 8: reserve the DOIs first (team lead, 2026-11-06)

The cards cross-link the three models by version DOI, so all three DOIs must exist before any card is final. Zenodo gives a draft deposition a pre-reserved DOI (`metadata.prereserve_doi`) as soon as the draft is created.

**htrmopo cannot publish into an existing draft.** In htrmopo 0.5, `publish_model` (`htrmopo publish`) always does everything in one call:
1. creates a new deposition;
2. takes that deposition's pre-reserved DOI as `id`;
3. uploads the card as `README.md`, then the files;
4. sets the Zenodo metadata;
5. publishes.

`update_model` (`htrmopo publish -d`) only makes a new version of a record that is already published. So the reserve step is done through the Zenodo deposit API. The upload and publish then repeat htrmopo's own steps against that draft.

Each step below needs its own go-ahead from the maintainer (item 8), and runs on the Zenodo sandbox first (`https://sandbox.zenodo.org/api/`, as htrmopo's `MODEL_REPO_URL`).

1. **Reserve.** Create three empty drafts: `POST deposit/depositions` with `{}`, one each for R4d, A1 and R3h. Note each draft's id and `metadata.prereserve_doi.doi`. Nothing is public yet, and an unpublished draft can still be deleted.
2. **Fill the cards.** Put the three reserved DOIs into each card's pipeline table and Citation section, and into each front matter's `id`. Rebuild each card as `---` + front matter + `---` + `card_body.md`. Validate it against the HTRMoPo v1 schema with htrmopo's own validator before any upload.
3. **Upload into each draft.** For each draft, through its bucket URL:
   - the card as `README.md`;
   - the four deposit files: the weights under their release name, `LICENSE`, `NOTICE` and the training record.
4. **Set the metadata.** Set it exactly as htrmopo 0.5 does: `title` from `summary`; `upload_type: publication`, `publication_type: other`; `description` from the card body rendered as HTML; `creators` from `authors`; `access_right: open`; `license`; `keywords` from `tags`; `related_identifiers` as `isDerivedFrom` the `datasets` URLs; and the `ocr_models` community. Community inclusion is a request that the repository's administrators approve.
5. **Check the drafts** in Zenodo's preview. This is the last point at which a deposit can be withdrawn.
6. **Publish** each draft (`POST deposit/depositions/<id>/actions/publish`). After this a deposit is permanent, which the maintainer has accepted (decision 0010).
7. **Mirror to Hugging Face:** three repositories, one per model. Each holds the Hugging Face card with the same DOIs, and the same four files.

Steps 1, 3, 4 and 6 call the API directly. A short script can reuse htrmopo's validator and metadata mapping, passing the draft's id instead of creating a new deposition.

The alternative would be to propose that change upstream: an option for htrmopo to publish into an existing deposition. It is not needed for this release.

## Before any deposit

- **Cards:** approved on 2026-11-06 (item 6). Plan step 2 adds the reserved DOIs; any other edit needs the maintainer's review again.
- **The accounts** (item 7).
- **Check the training records again** for local paths at deposit time (proposal §4).
- **The reserved version DOIs** in each card's Citation section and pipeline table (plan step 2).
