# First release: R4d + A1 + R3h (drafts)

**Status: published on Zenodo on 2026-11-07** (R4d [10.5281/zenodo.24023070](https://doi.org/10.5281/zenodo.24023070), A1 [10.5281/zenodo.24023072](https://doi.org/10.5281/zenodo.24023072), R3h [10.5281/zenodo.24023074](https://doi.org/10.5281/zenodo.24023074)). **Mirrored on Hugging Face on 2026-11-07** ([R4d](https://huggingface.co/HeOCR/heocr-r4d-segmentation), [A1](https://huggingface.co/HeOCR/heocr-a1-reading-order), [R3h](https://huggingface.co/HeOCR/heocr-r3h-recognition)). The maintainer approved the three cards and the three NOTICE files on 2026-11-06, and the DOI lines on 2026-11-07.
- That approval closes sign-off item 6 in [the release proposal](../planning/proposals/model-release.md) §7, for the cards as they stand at `952e5b5` (decision 0011's note).
- The accounts (item 7) and each publishing step (item 8) are done (decision 0011's note).

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

Since decision 0014 (2026-11-10), the steps need no per-step go-ahead; item 8 is superseded. The whole plan runs first on the Zenodo sandbox (`https://sandbox.zenodo.org/api/`, with the sandbox token), and then on production. Paths are InvenioRDM's records API under `/api/`. The community-review and inclusion calls are to be confirmed on the sandbox before production.

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
7. **Mirror to Hugging Face:** the three repositories above. **Done 2026-11-07** (decision 0011's note). Each gets the Hugging Face card, with the same DOIs, and the same four files. `release/hf_upload.py` does this.
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

`release/zenodo_deposit.py` runs the API steps. Each run is one step (no per-step go-ahead since decision 0014).
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

# Second release: R6 (Tesseract), a deposit of its own

**Status: drafts, nothing reserved or published.** The maintainer said "Yes, release R6" on 2026-11-10, and decision 0014 needs no per-step go-ahead. Terms: Apache-2.0, licensed by "HeOCR maintainers", as decisions 0010 and 0014; inputs under decision 0015 (NLI "public domain, free use" scans, credited in the NOTICE).

| Model | Release file | Trained as | sha256 | Folder |
|---|---|---|---|---|
| R6 | `heocr_r6.traineddata` | `heb.traineddata` | `73eb18e03f8793dff9c03699db0845779f6b5db4897824bcd61787245ec66e10` | `r6/` |

R6 fine-tunes tessdata_best `heb` on 13,648 real NLI scan lines labelled with Project Ben-Yehuda text (`docs/baselines.md`, R3j/R5/R6 section). Users run it as `tesseract … -l heocr_r6 --tessdata-dir DIR --psm 3`. The release name is a Tesseract language name, so it uses an underscore, like tessdata's `chi_sim`. (Tesseract 5.5.3 also loads a hyphenated name; the underscore follows the convention.)

**How it differs from the first release:**
- **Its own record, its own DOI.** R6 is not part of the kraken pipeline. Its card links to none of the R4d, A1 and R3h DOIs, and their cards are unchanged.
- **Not HTRMoPo.** `r6/zenodo.yaml` uses the keys the deposit script maps (`summary`, `authors`, `license`, `tags`, `communities`), plus `related`: `isDerivedFrom` links with their own resource type (the tessdata_best base as `software`, the five NLI IIIF manifests as `image`, the Ben-Yehuda dump as `dataset`). It has no `software_hints`, and the card is not validated against the HTRMoPo v1 schema. A plain check (`validate_plain`) requires `id`, `summary`, `authors` and the Apache-2.0 licence, and refuses `ocr_models`.
- **Community `heocr` only.** `ocr_models` is the kraken/HTRMoPo listing that `kraken list` and `htrmopo list` read; a `.traineddata` does not belong there.
- **Creators** are the first release's, exactly: Shay Palachy Affek (person, ORCID iD 0000-0002-1459-9320) and "HeOCR maintainers" (organisation).
- **The training record** is `heocr_tesseract_training_run.v1`, below.

## Files in `r6/`

The same set as the first release's folders: `card_body.md`, `zenodo.yaml`, `huggingface.yaml`, `NOTICE`, `LICENSE` (byte-identical to the others) and `r6_training_run.json`. A card for either venue is its front matter between `---` lines, followed by `card_body.md`. The Hugging Face front matter has no `base_model`, because that field takes a Hub repository id and tessdata_best is not on the Hub.

### `heocr_tesseract_training_run.v1`

`heocr_engine_training_run.v1` does not fit a Tesseract run:
- it describes ketos runs made by `heocr-engine train-kraken`;
- its `init` must be `from_scratch` or a fine-tune of a project recognizer with its own record, while R6 starts from a third-party model;
- its `data` must be a hocrsyngen batch, with annotations and generation-manifest sha256s;
- its `text_order` assumes kraken's display-order reordering.

So R6's record is a minimal equivalent with the same top-level sections where they apply, written by hand from the task's scripts, logs and outputs. `tests/test_release_r6.py` checks it.

| Section | Holds |
|---|---|
| `schema_version`, `schema_note` | `heocr_tesseract_training_run.v1`, and why it is not the engine format |
| `engine`, `trainer` | Tesseract 5.5.3; `lstmtraining`, `lstmeval` and `combine_tessdata`, with executable sha256s |
| `init` | the third-party base (repository, commit, git blob, sha256, licence, version string, extracted LSTM sha256), the starter traineddata (unicharset, dictionary, langdata_lstm build files) and the network |
| `data` | the line set's manifest, summary and PNG hashes; label source, normalisation and gates; the scans' holder, licence label, attribution and route; each training and selection record with its lines and US status |
| `truth_order` | logical ground truth, and the LSTM training order |
| `commands` | argument lists with `<placeholders>` for local files: `.lstmf` conversion, both training arms, selection and conversion |
| `hyperparameters`, `run`, `outcome` | the two arms, the selection rule and the selected checkpoint |
| `evaluation` | the scored set, scorer, results with intervals, and the word 6-gram text-overlap check |
| `output` | sha256, bytes, training and release file names, language name, format |
| `model_licence` | Apache-2.0, `basis` decision 0014, `published: false` |

## The scripts for R6

Both scripts take `--models r6`. The default `--models` stays `r4d a1 r3h`, and for that default their requests and output are byte-identical to before (checked by running `main`'s scripts and this branch's against the same fake server).
- **One release per run, one state file per release.** A run that names `r6` with any of `r4d`, `a1`, `r3h`, or that uses a state file holding the other release's drafts, is refused. Use a separate state file, for example `~/.config/heocr/zenodo-production-r6-state.json` (and `…-sandbox-r6-state.json`).
- **`reserve` honours `--models`.** It used to reserve all three first-release models whatever `--models` said; with the default it still does.
- **`plan`** (new) prints what `reserve`, `upload`, `metadata` and `publish` would send for each model: the card format and DOI check, the files with their sha256s, the metadata without the description, and the communities. It makes no network call, needs no token and never writes the state file. Before step 1 it skips the card's citation check, which `upload` and `metadata` make once the DOI exists.

## Plan for R6

**Status: published on 2026-11-10.** Zenodo [10.5281/zenodo.24109989](https://doi.org/10.5281/zenodo.24109989) (record 24109989, accepted into `heocr`), mirrored on Hugging Face as [HeOCR/heocr-r6-tesseract-heb](https://huggingface.co/HeOCR/heocr-r6-tesseract-heb).
- **Checks:** the sandbox run (draft 638698) came first. The production draft was checked before publishing: the file's md5 matched, and the creators, licence, DOI, 5 files and 7 related links were all right.
- **After publishing:** the Hugging Face file's sha256 matches the record, and Tesseract 5.5.3 loads `-l heocr_r6` from it.

Sandbox first, then production, as for the first release. Tokens come from the environment only: `ZENODO_SANDBOX_TOKEN`, `ZENODO_TOKEN` and `HF_TOKEN`, which the maintainer's Codex helper will provide. No agent creates an account or handles a token in any file.

```sh
S=~/.config/heocr/zenodo-production-r6-state.json   # outside the repository; R6 only
python release/zenodo_deposit.py --models r6 --production --state $S plan --weights r6=…/heb.traineddata  # any time, offline
python release/zenodo_deposit.py --models r6 --production --state $S reserve                             # step 1
python release/zenodo_deposit.py --models r6 --production --state $S upload --weights r6=…/heb.traineddata  # step 3
python release/zenodo_deposit.py --models r6 --production --state $S metadata                            # step 4
python release/zenodo_deposit.py --models r6 --production --state $S publish                             # step 6
python release/zenodo_deposit.py --models r6 --production --state $S accept                              # step 6: heocr
python release/hf_upload.py --models r6 --zenodo-state $S --weights r6=…/heb.traineddata                 # step 7
```

1. **Reserve** one draft and its DOI. Nothing is public yet.
2. **Fill the card by PR:** replace the `DRAFT` comment in the Citation section of `r6/card_body.md` with the reserved version DOI. That is the only change. The DOI goes nowhere else: no other card links to R6, and R6 links to no other record.
3. **Upload** the card as `README.md`, then `heocr_r6.traineddata` (the trained `heb.traineddata` is uploaded under its release name; `upload` refuses it unless its sha256 matches the record), `LICENSE`, `NOTICE` and `r6_training_run.json`.
4. **Set the metadata:** the title from `summary`, the description from the card body, the creators, the licence, keywords from `tags` and the `related` links.
5. **Check the draft** in Zenodo's preview.
6. **Publish,** then request inclusion in `heocr` and accept it with `accept`.
7. **Mirror to Hugging Face:** `HeOCR/heocr-r6-tesseract-heb`, created public if needed, with the card (`huggingface.yaml` + `card_body.md`, citing the DOI) and the same four files in one commit.

**To confirm on the sandbox:** that Zenodo accepts the resource types `software` and `image` in `related` links (the first release used only `dataset`). If it does not, change them in `r6/zenodo.yaml` before production.

**At deposit time:** check the training record again for local paths (the test does), and record the DOI and the publication in a planning note, as for the first release.

# Third release: R7 (Tesseract), a deposit of its own

**Status: drafts, nothing reserved or published.** Decision 0014 needs no per-step go-ahead. Terms: Apache-2.0, licensed by "HeOCR maintainers", as R6; inputs under decision 0015 (NLI "public domain, free use" scans and Internet Archive library scans, both credited in the NOTICE).

| Model | Release file | Trained as | sha256 | Folder |
|---|---|---|---|---|
| R7 | `heocr_r7.traineddata` | `heb.traineddata` | `95faab81fba6fe57f854f973c1ccad2b0d1059fb951f34b17277385ceea8b303` | `r7/` |

R7 is R6's recipe on a larger line set: tessdata_best `heb` (the same base and the same starter as R6, not R6 itself) fine-tuned on 95,151 real lines of `bynli_lines_v2`, from 7 NLI books and 23 Internet Archive books, labelled with Project Ben-Yehuda text. Users run it as `tesseract … -l heocr_r7 --tessdata-dir DIR --psm 3`.

**What the card says.** R7 beats stock Tesseract and tessdata_best on the 38 E2d4c pages, by about 0.016 CER and 0.08–0.09 WER. It ties R6 on CER (R7 − R6 = −0.0005 [−0.0072, +0.0061]), its WER is slightly lower within the interval, and on the 10 hardest pages it is no better than stock or R6. **R7 supersedes nothing; R6 remains valid.** R6's card, record and deposit are unchanged.

**How it differs from R6:**
- **Two scan routes.** The NOTICE credits NLI with every record id, and the Internet Archive with every identifier and its contributing library. For the Internet Archive items it states that the original conditions of each item on the Internet Archive still apply: they are published there without an explicit licence (hocrgen decision 2026-11-10, open release, item 2).
- **Rights justifications.** Each Internet Archive book carries the ids of its `hocrgen.rights_justification.v1` records (one per Ben-Yehuda work) in `r7_training_run.json`, as hocrgen's legal-strategy decision asks of a release's provenance file. All 23 were checked against the f8f_ia `editions.json` before the NOTICE was written: each is accepted, its id matches the line set's, its digitizer is a university library (none Google, none NLI), and every recorded death year is more than 70 years ago.
- **`related` links:** the base as `software`, the 7 NLI IIIF manifests and the 23 Internet Archive items (`https://archive.org/details/<identifier>`) as `image`, and the Ben-Yehuda dump as `dataset`: 32 in all.
- **No link to R6's record.** The script maps every `related` item to `isDerivedFrom`, and R7 is not derived from R6. `isNewVersionOf` would say that R7 replaces R6, which it does not, and R7 is a record of its own, not a Zenodo version of R6's. The card body names R6 and its DOI instead.

## Files in `r7/`

The same set as `r6/`: `card_body.md`, `zenodo.yaml`, `huggingface.yaml` (for `HeOCR/heocr-r7-tesseract-heb`), `NOTICE`, `LICENSE` (byte-identical) and `r7_training_run.json`. `tests/test_release_r7.py` checks them.

The record is `heocr_tesseract_training_run.v1`, with R6's top-level sections in R6's order. Where R7 has more than R6:
- `data.scans` is a list with one entry per route (`nli_free_use`, `internet_archive`). R6's single object is the one-route case.
- Each `data.train` and `data.selection` entry has a `source`. NLI entries keep R6's keys. Internet Archive entries have `ia_identifier`, `contributing_library`, `pby_works` (each with its `rights_justification_id`), `death_years`, `publication_year`, `israel_status`, `us_status` and the justification's one-line summary.
- `data.gates.training_list_filters` records the two filters applied after `.lstmf` conversion: train lines sharing a word 6-gram with a dev line, and lines with characters outside the starter's set.
- `evaluation.results` gives four decimals, each delta's WER interval and page counts, and the paired comparison against R6.

## The scripts for R7

Both scripts take `--models r7`, exactly as `--models r6`. `SEPARATE_RELEASES` is now `("r6", "r7")`: R6 and R7 are separate releases, so a run naming both, or a state file holding the other's draft, is refused. The default `--models` stays `r4d a1 r3h`. Use an R7-only state file, for example `~/.config/heocr/zenodo-production-r7-state.json`.

## Plan for R7

**Status: published on 2026-11-11.**
- **Where:** Zenodo [10.5281/zenodo.24126449](https://doi.org/10.5281/zenodo.24126449) (record 24126449; community request f83fc631 accepted into `heocr`), mirrored on Hugging Face as [HeOCR/heocr-r7-tesseract-heb](https://huggingface.co/HeOCR/heocr-r7-tesseract-heb).
- **No sandbox run.** R7 reuses R6's code path, which was proven in the sandbox and then in production.
- **Checks before publishing:** the production draft's 5 files were complete; the weights' md5 matched the local model; and the creators, the Apache-2.0 licence and the 32 related links (23 of them `archive.org`, which resolve) were all right.
- **After publishing:** the files downloaded from Zenodo and from Hugging Face both have sha256 `95faab81…`, and Tesseract 5.5.3 loads `-l heocr_r7` from the Zenodo copy. Its output on an E2d4c page is the same as the scored prediction.

The same seven steps as R6, sandbox first:

```sh
S=~/.config/heocr/zenodo-production-r7-state.json   # outside the repository; R7 only
python release/zenodo_deposit.py --models r7 --production --state $S plan --weights r7=…/heb.traineddata  # any time, offline
python release/zenodo_deposit.py --models r7 --production --state $S reserve                             # step 1
python release/zenodo_deposit.py --models r7 --production --state $S upload --weights r7=…/heb.traineddata  # step 3
python release/zenodo_deposit.py --models r7 --production --state $S metadata                            # step 4
python release/zenodo_deposit.py --models r7 --production --state $S publish                             # step 6
python release/zenodo_deposit.py --models r7 --production --state $S accept                              # step 6: heocr
python release/hf_upload.py --models r7 --zenodo-state $S --weights r7=…/heb.traineddata                 # step 7
```

1. **Reserve** one draft and its DOI.
2. **Fill the card by PR:** replace the `DRAFT` comment in the Citation section of `r7/card_body.md` with the reserved version DOI, and update `tests/test_release_r7.py` to expect it, as #68 did for R6.
3. **Upload** the card as `README.md`, then `heocr_r7.traineddata` (refused unless its sha256 matches the record), `LICENSE`, `NOTICE` and `r7_training_run.json`.
4. **Set the metadata.**
5. **Check the draft** in Zenodo's preview. Its 32 related links include 23 `archive.org` URLs, which no earlier record had.
6. **Publish,** then request inclusion in `heocr` and accept it with `accept`.
7. **Mirror to Hugging Face:** `HeOCR/heocr-r7-tesseract-heb`.

`plan` was run offline on this branch with no state file, once without weights and once with the trained `heb.traineddata`: the plain card check passed, the weights matched the record's sha256 (3,628,595 bytes), and it listed 5 files, 32 related links and the `heocr` community.

# Fourth release: R8b (Tesseract), a deposit of its own

**Status: published on 2026-11-12** (see [Plan for R8b](#plan-for-r8b)). Decision 0014 needs no per-step go-ahead. Terms: Apache-2.0, licensed by "HeOCR maintainers", as R6 and R7. Inputs follow decisions 0015 and 0016, and every one is credited in the NOTICE.

| Model | Release file | Trained as | sha256 | Folder |
|---|---|---|---|---|
| R8b | `heocr_r8b.traineddata` | `heb.traineddata` | `8cb22dbeb195c3c0ffbe9c66cf956d8c2052d3b1c4a872234a85c975c4526117` | `r8b/` |

R8b continues from R7's weights (the checkpoint R7 was packed from) for one epoch over 196,275 lines:
- R7's lines plus 145 lines with ׳ ״ —;
- 15 more books (`bynli_lines_v3`);
- 48 born-digital Reshumot booklets;
- 11 Wikisource lines;
- 18,627 synthetic lines.

Its character set is the R8 starter's (73 codes), and it is 3,633,477 bytes. Users run it as `tesseract … -l heocr_r8b --tessdata-dir DIR --psm 3`.

**What the card says.** All figures come from eval's frozen `r8b_release_figures_v1.json` (sha256 `22c0305d…`), under the `line_fold_v1` profile.
- **OLB Reshumot dev set (silver; not a test score):** R8b beats R7 on all lines (2.129 against 2.934 CER) and on the exact stratum (0.735 against 1.320), and no interval reaches zero.
- **Held-out selection books:** R8b beats R7 on both, with a selection-optimism caveat.
- **Brainin's Internet Archive scan:** R8b is worse than R7 (0.743 against 0.635).
- **No human-reviewed test score yet.**
- **R8b supersedes nothing; R7 remains valid.** R7's card, record and deposit are unchanged.

**How it differs from R7:**
- **Four Google-digitized Internet Archive scans.** Each is credited as "Digitized by Google; retrieved via the Internet Archive" with its contributing library ("unknown library" for `mikhtavimmiarsh00mezagoog`). They are admitted under rule 3 of hocrgen's legal strategy and decision 0015. The NOTICE and the record give each one's hygiene: canvas 0 excluded, no watermark found, no training line from canvas 0.
- **New sources:**
  - Reshumot laws and regulations: PD-IL under Copyright Act 2007 §6, with no status asserted outside Israel;
  - one Wikisource page: CC BY-SA 4.0 text, credited under decision 0016;
  - the CC0 synthetic add-on: generator and recipe in HeOCR/hocrsyngen `3b55d4a`, under `experiments/learned_generation_v0/s17a_scanifier/`.
- **Word list:** checked by decoding rather than by bytes. The dawg is rebuilt for a larger character set, so byte identity with tessdata_best cannot hold. Decoded, R8b's list is identical to R7's: tessdata_best's 70,171 entries in right-to-left order. No entry comes from any training text.
- **`related` links:** 49 in all:
  - the base and R7 (`https://doi.org/10.5281/zenodo.24126449`) as `software`. R8b is derived from R7, so `isDerivedFrom` is right here. It is still a record of its own, not a Zenodo version of R7's;
  - 8 NLI manifests, 37 `archive.org` items and the Commons file as `image`;
  - the Ben-Yehuda dump as `dataset`.

  The 48 Reshumot booklets are not linked, because their publisher URLs are opaque API links. Each one's URL and PDF sha256 are in the record.
- **Hugging Face:** `base_model: HeOCR/heocr-r7-tesseract-heb` (`finetune`), since R7 is on the Hub.

## Files in `r8b/`

The same set as `r7/`: `card_body.md`, `zenodo.yaml`, `huggingface.yaml` (for `HeOCR/heocr-r8b-tesseract-heb`), `NOTICE`, `LICENSE` (byte-identical) and `r8b_training_run.json`. `tests/test_release_r8b.py` checks them, including that the card's figures match the record's copy of eval's frozen figures.

The record is `heocr_tesseract_training_run.v1`, with R7's top-level sections in R7's order. Where R8b differs:
- `init.kind` is `continue_from_project_model`, and `init.from_model` names R7's checkpoint, DOI and sha256s.
- `data.line_sets` replaces the single `line_set` and `manifest_sha256`, with one entry per line set.
- Each `data.train` entry has a `line_set` and a `source`:
  - `nli_free_use`;
  - `internet_archive`, with `source_class`, `digitizer` and, for Google scans, a `google` block;
  - `reshumot_born_digital`, one entry per booklet;
  - `wikimedia_commons`;
  - `synthetic`.
- `data.rights_verification` records the per-row check.
- `evaluation`:
  - cites the frozen figures and their sha256;
  - copies the OLB gate, the held-out books and the report sets from them;
  - adds `text_overlap_check` (eval's `check_train_overlap.py` counts, and the audit2 6-gram check) and `word_list_check`.

## The scripts for R8b

Both scripts take `--models r8b`, exactly as `--models r7`. `SEPARATE_RELEASES` is now `("r6", "r7", "r8b")`, and the default `--models` stays `r4d a1 r3h`. Use an R8b-only state file, for example `~/.config/heocr/zenodo-production-r8b-state.json`.

## Plan for R8b

**Status: published on 2026-11-12.**
- **Where:** Zenodo [10.5281/zenodo.24156688](https://doi.org/10.5281/zenodo.24156688) (record 24156688, concept 24156687; community request 452272b4 accepted into `heocr`), mirrored on Hugging Face as [HeOCR/heocr-r8b-tesseract-heb](https://huggingface.co/HeOCR/heocr-r8b-tesseract-heb) (`base_model` HeOCR/heocr-r7-tesseract-heb).
- **No sandbox run.** R8b reuses R6's and R7's code path.
- **Checks before publishing:** the reserved DOI is the version DOI (prereserve recid 24156688; the concept record is 24156687); the production draft's 5 files were complete; the weights' md5 (`74f05d63…`) matched the local model; the creators, the Apache-2.0 licence and the 49 related links (R7's DOI among them, as `isDerivedFrom`) were all right; the description carries the DOI.
- **After publishing:** the files downloaded from Zenodo and from Hugging Face both have sha256 `8cb22dbe…`, and Tesseract 5.5.3 loads `-l heocr_r8b` from the Zenodo copy and reads a Kevar selection line as its label.

The same seven steps as R7:

```sh
S=~/.config/heocr/zenodo-production-r8b-state.json   # outside the repository; R8b only
python release/zenodo_deposit.py --models r8b --production --state $S plan --weights r8b=…/heb.traineddata  # any time, offline
python release/zenodo_deposit.py --models r8b --production --state $S reserve                              # step 1
python release/zenodo_deposit.py --models r8b --production --state $S upload --weights r8b=…/heb.traineddata  # step 3
python release/zenodo_deposit.py --models r8b --production --state $S metadata                             # step 4
python release/zenodo_deposit.py --models r8b --production --state $S publish                              # step 6
python release/zenodo_deposit.py --models r8b --production --state $S accept                               # step 6: heocr
python release/hf_upload.py --models r8b --zenodo-state $S --weights r8b=…/heb.traineddata                  # step 7
```

1. **Reserve** one draft and its DOI.
2. **Fill the card by PR:** replace the `DRAFT` comment in the Citation section of `r8b/card_body.md` with the reserved version DOI, and update `tests/test_release_r8b.py` to expect it, as #71 did for R7.
3. **Upload** the card as `README.md`, then `heocr_r8b.traineddata` (refused unless its sha256 matches the record), `LICENSE`, `NOTICE` and `r8b_training_run.json`.
4. **Set the metadata.**
5. **Check the draft** in Zenodo's preview, including the 49 related links and R7's DOI among them.
6. **Publish,** then request inclusion in `heocr` and accept it with `accept`.
7. **Mirror to Hugging Face:** `HeOCR/heocr-r8b-tesseract-heb`.

`plan` was run offline on this branch with no state file, once without weights and once with the packed `r8b-main-fold` `heb.traineddata`. The plain card check passed, and the weights matched the record's sha256 (3,633,477 bytes). It listed 5 files, 49 related links and the `heocr` community. No state file was written.
