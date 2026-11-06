# First release: R4d + A1 + R3h (drafts)

**Status: published on Zenodo on 2026-11-07** (R4d [10.5281/zenodo.24023070](https://doi.org/10.5281/zenodo.24023070), A1 [10.5281/zenodo.24023072](https://doi.org/10.5281/zenodo.24023072), R3h [10.5281/zenodo.24023074](https://doi.org/10.5281/zenodo.24023074)). **The Hugging Face mirror is pending.** The maintainer approved the three cards and the three NOTICE files on 2026-11-06, and the DOI lines on 2026-11-07.
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

**Accounts (item 7, maintainer, 2026-11-06):**
- **Zenodo:** deposited from Shay's personal Zenodo account, into a new HeOCR community that Shay creates. Each record is also submitted to `ocr_models`, the kraken/HTRMoPo model community that `kraken list` and `htrmopo list` read. Without it the models stay findable by DOI but are not listed there. Inclusion is a request that the community's administrators approve.
- **Zenodo creators:**
  - Shay Palachy Affek, as a person: family name "Palachy Affek", given name "Shay", ORCID iD [0000-0002-1459-9320](https://orcid.org/0000-0002-1459-9320). The name split and the iD are as on his ORCID record (2026-11-06).
  - "HeOCR maintainers", as an organisation.
- **Hugging Face:** a new HeOCR organisation that Shay creates, with three repositories: `HeOCR/heocr-r3h-recognition`, `HeOCR/heocr-r4d-segmentation` and `HeOCR/heocr-a1-reading-order`. They are named like the release files.

**Zenodo: three records,** one per model, in htrmopo's deposit format: the card as `README.md`, plus four files.
- **The files:**
  - the weights, under their release name;
  - `LICENSE`;
  - `NOTICE`;
  - the training record.
- **Assembly:** the deposit directory is assembled outside the repository, since the weights never enter git.
- **Front matter:** it keeps `metrics` and `software_hints` as written. `ketos publish` would replace both, and would upload only the weights and a generated `metadata.json`, so it is not used.
- **Validation:** validate each card locally against the HTRMoPo v1 schema before any upload.

**Why not `htrmopo publish` itself.** htrmopo 0.5 (`publish_model`) does every step in one call:
1. it creates a new deposition through Zenodo's legacy deposit API;
2. it takes that deposition's pre-reserved DOI as `id`;
3. it uploads the card as `README.md`, then the files;
4. it sets the metadata;
5. it publishes.

Two things it cannot do:
- **Publish into an existing draft.** `update_model` (`htrmopo publish -d`) only versions a record that is already published. Reserving the DOIs first needs drafts that exist before any card is final.
- **Mark a creator as an organisation.** htrmopo passes `authors` unchanged as the legacy API's `creators`, and those have only `name`, `affiliation`, `orcid` and `gnd`, with names as "Family, Given". There is no creator type, so "HeOCR maintainers" would be filed as a person. HTRMoPo's own `authors` items also have only `name`, `affiliation` and `orcid`.

Zenodo's InvenioRDM records API has both. A draft can reserve its DOI before anything is final, and a creator's `person_or_org.type` is `personal` (with `given_name` and `family_name`) or `organizational` (with `name`), with an ORCID under `identifiers`. So the deposit uses a short script against the records API.
- It reads the HTRMoPo front matter.
- It maps `authors` by their `type` key, which is an extra key that the HTRMoPo schema allows and htrmopo ignores:
  - **`personal`:** `{"person_or_org": {"type": "personal", "family_name": "Palachy Affek", "given_name": "Shay", "identifiers": [{"scheme": "orcid", "identifier": "0000-0002-1459-9320"}]}}`. The family and given names are split at the comma in `name`. The ORCID goes under `person_or_org.identifiers` as the bare iD; `zenodo.yaml` holds the `https://orcid.org/` URL, because HTRMoPo's `orcid` is a URI.
  - **`organizational`:** `{"person_or_org": {"type": "organizational", "name": "HeOCR maintainers"}}`.
- It uploads the same card and files that htrmopo would, so htrmopo's readers see the usual HTRMoPo record.
- Its metadata otherwise follows htrmopo's mapping: the title from `summary`, the description from the card body, and the licence, keywords and `isDerivedFrom` links to the `datasets`.

**Hugging Face: three repositories,** mirroring the Zenodo records. Each holds:
- `README.md`, made of the `huggingface.yaml` front matter plus `card_body.md`;
- the weights, `LICENSE`, `NOTICE` and the training record.

## Before step 1

Shay does these himself. None of them is an agent action.
- **Create the Zenodo community** for HeOCR. **Done:** `heocr` (https://zenodo.org/communities/heocr): public, with an open record submission policy and a closed review policy. It is set in the three `zenodo.yaml` files.
- **Create the Hugging Face organisation.** **Done:** https://huggingface.co/HeOCR.
- **Confirm the name split and ORCID iD.** **Done** from his ORCID record: "Palachy Affek, Shay", 0000-0002-1459-9320.
- **Create the tokens:**
  - a **Zenodo sandbox** token (on sandbox.zenodo.org) and a **Zenodo production** token, each with the scopes `deposit:write` (create and edit drafts) and `deposit:actions` (publish);
  - a **Hugging Face** write token for the HeOCR organisation.
- **Store the tokens outside every repository,** for example:
  - in the macOS Keychain;
  - or in `~/.config/heocr/release.env` with `chmod 600`.

  They go into no repository, no task folder and no record.
- **Scripts read the tokens from the environment only:** `ZENODO_TOKEN`, `ZENODO_SANDBOX_TOKEN` and `HF_TOKEN`. They never write a token to a log, a file, a command line, an error message or a commit, and they never pass it in a URL. Zenodo's legacy API accepts `?access_token=`; the script sends an `Authorization: Bearer` header instead.

## Plan for item 8: reserve the DOIs first (team lead, 2026-11-06)

The cards cross-link the three models by version DOI, so all three DOIs must exist before any card is final.

Each step needs its own go-ahead from the maintainer (item 8). The whole plan runs first on the Zenodo sandbox (`https://sandbox.zenodo.org/api/`, with the sandbox token), and then on production. Paths are InvenioRDM's records API under `/api/`. The community-review and inclusion calls are to be confirmed on the sandbox before production.

1. **Reserve.** Create three drafts, `POST /api/records`, one each for R4d, A1 and R3h, with the creators mapped as above. Reserve each draft's DOI with `POST /api/records/{id}/draft/pids/doi`, and note it. Nothing is public yet, and an unpublished draft can still be deleted.
2. **Fill the cards.**
   - Put the three reserved DOIs into each card's pipeline table and Citation section, and into each front matter's `id`.
   - Rebuild each card as `---`, then the front matter, then `---`, then `card_body.md`.
   - Validate each card against the HTRMoPo v1 schema with htrmopo's validator.
   - These DOIs are the only change to the approved cards (decision 0011's note).
3. **Upload into each draft.** For each file:
   - start it: `POST /api/records/{id}/draft/files`;
   - upload its content: `PUT …/files/{name}/content`;
   - commit it: `POST …/files/{name}/commit`.

   The files are the card as `README.md`, then the weights under their release name, `LICENSE`, `NOTICE` and the training record.
4. **Set the metadata,** following htrmopo's mapping:
   - the title from `summary`;
   - the description from the card body;
   - the creators;
   - the licence;
   - keywords from `tags`;
   - `isDerivedFrom` links to the `datasets` URLs.

5. **Check the drafts** in Zenodo's preview. This is the last point at which a deposit can be withdrawn.
6. **Publish** each draft: `POST /api/records/{id}/draft/actions/publish`. After this a deposit is permanent, which the maintainer has accepted (decision 0010). Then request inclusion in both communities, `heocr` and `ocr_models` (`POST /api/records/{id}/communities`). Shay's account accepts `heocr`'s requests through the API: the script's `accept` command, which re-reads each request and accepts only requests to `heocr`, by its id on that target. It was checked on the sandbox on 2026-11-06. `ocr_models` needs that community's approval, and `accept` never touches its requests. The team lead confirmed on 2026-11-06 that the records go to `ocr_models` as well as HeOCR, for `kraken list` discovery.
7. **Mirror to Hugging Face:** the three repositories above. Each gets the Hugging Face card, with the same DOIs, and the same four files. `release/hf_upload.py` does this.
   - It creates each public repository under HeOCR if it does not exist yet, then adds the card and the four files in one commit.
   - It takes each model's DOI from the production Zenodo state file, and refuses a card that does not cite it.
   - It refuses weights whose sha256 differs from the record.
   - It reads `HF_TOKEN` from the environment only.
   - `--dry-run` prints the plan with no network and no token:

   ```sh
   python release/hf_upload.py --dry-run --zenodo-state ~/.config/heocr/zenodo-production-state.json --weights r4d=… a1=… r3h=…
   ```

   Hugging Face has no sandbox. The dry run was checked against the sandbox copy (`--release-dir`, dry runs only).

An upstream htrmopo change would remove the need for the script: publishing into an existing draft, and creator types. It is not needed for this release.

### The deposit script

`release/zenodo_deposit.py` runs the API steps. Each run is one step, and each step needs its go-ahead.
- **Target:** the sandbox, unless `--production` is given.
- **Token:** read from `ZENODO_SANDBOX_TOKEN`, or from `ZENODO_TOKEN` with `--production`. It is sent only as a Bearer header and redacted from errors.
- **State file:** holds only draft ids and DOIs, kept private (`chmod 600`). It must be outside the repository, and one file serves one target.
- **Requirements:** PyYAML, Markdown and htrmopo, to read, render and validate the cards. Its offline tests (`tests/test_zenodo_deposit.py`) mock the HTTP layer and need none of them.

```sh
python release/zenodo_deposit.py --state ~/.config/heocr/zenodo-sandbox-state.json reserve     # step 1
python release/zenodo_deposit.py --state … upload --weights r4d=… a1=… r3h=…                   # step 3
python release/zenodo_deposit.py --state … metadata                                            # step 4
python release/zenodo_deposit.py --state … publish                                             # step 6
python release/zenodo_deposit.py --state … accept                                              # step 6: heocr's requests
python release/zenodo_deposit.py --state … status                                              # no network
```

- **Step 2** (filling in the DOIs, by PR) and **step 5** (checking the previews) are done by hand.
- **`upload` and `metadata` refuse a card that does not cite its own reserved DOI.** `upload` also refuses weights whose sha256 differs from the training record.
- **Checked on the sandbox (step 1, 2026-11-06):**
  - draft creation and DOI reservation work;
  - the typed creators (person with ORCID, organisation) and `publication-other` are kept as sent;
  - Zenodo returns InvenioRDM's own JSON only for `Accept: application/vnd.inveniordm.v1+json`. With `application/json` it returns its legacy serialization, which has no `pids`. The script sends the InvenioRDM type.
- **`reserve` is crash-safe:** it saves each draft's id before reserving its DOI, and a rerun reserves the missing DOI instead of creating a second draft.
- **Not yet checked against a live server:** the community-inclusion call, `POST /records/{id}/communities` after `GET /communities/{slug}`.

## Before any deposit

- **Cards and NOTICEs:** approved on 2026-11-06 (item 6, and item 4's NOTICE text), and pinned by sha256 in decision 0011's note. Plan step 2 adds the reserved DOIs to the cards. Any other edit to either needs the maintainer's review again.
- **Accounts:** decided on 2026-11-06 (item 7). See "Before step 1" for what Shay sets up.
- **Check the training records again** for local paths at deposit time (proposal §4).
- **The reserved version DOIs** in each card's Citation section and pipeline table (plan step 2).
