# Training-run contract: `heocr_engine_training_run.v1`

One JSON object per training run (a recognizer, a baseline segmenter with `task: "segmentation"`, or a reading-order model with `task: "reading_order"`), UTF-8, written without NaN or infinity by `heocr-engine train-kraken` or `heocr-engine train-kraken-seg`. Reading-order records are written from the run's evidence (see [Reading-order runs](#reading-order-runs)). It records what a model was trained on and how, so that a score can be traced to a model hash and the model to its data. It makes no accuracy claim, and it contains no local paths.

## Input: `hocrsyngen_line_annotations.v1`

The training data is a hocrsyngen batch: its `generation_manifest.json`, its page images, and the opt-in `line_annotations.json` sidecar:

```json
{"schema": "hocrsyngen_line_annotations.v1", "generation_manifest_sha256": "<64 hex>",
 "coordinate_space": "final_page_pixels",
 "pages": [{"sample_id": "…", "page_id": "…", "page_sha256": "<64 hex>", "width": 1200, "height": 1600,
            "lines": [{"line_index": 0, "region": "body", "text": "שלום 96",
                       "polygon": [[x, y], …], "baseline": [[x, y], …],
                       "logical_line_index": 0, "logical_join": null, "occluded": false}]}]}
```

A physical line is not a logical line. Body text wraps, and each ledger cell is drawn as its own line. `logical_line_index` points into the sample's `text.logical_order.split("\n")` in the manifest. It is `null` for text that is drawn on the page but is absent from `logical_order`, such as stamps and marginalia. `logical_join` is `"space"` for a wrap continuation, `"cell"` for a ` | ` table cell, or `null` for the first segment. `occluded` is true when a stamp or overlay polygon overlaps the line. Training uses physical lines and each line's own `text`. Lines outside `logical_order` are trained on, because their text is really drawn; occluded lines are trained on and counted.

The converter fails closed unless:

- `generation_manifest_sha256` is the sha256 of the manifest file it is given;
- every page appears in the manifest with the same `sample_id`, `page_sha256`, `width` and `height`, and the image bytes hash to `page_sha256`. Asset paths must stay inside the manifest's directory;
- coordinates are integers inside the page, polygons have at least 3 points and baselines at least 2;
- `text` is non-empty NFC with no control characters, no line or paragraph separators, no invisible bidi controls (LRM, RLM, ALM, embeddings, overrides, isolates) and no leading or trailing whitespace. Text is in logical order;
- baselines run left to right in pixel x (first x below last, never decreasing);
- `logical_line_index` is `null` or an index into the manifest's `logical_order` lines, `logical_join` is `null`, `"space"` or `"cell"` (and `null` when `logical_line_index` is `null`), and `occluded` is a boolean;
- `line_index` values are unique within a page, and no page image appears twice.

## Conversion and split

`heocr-engine prepare-kraken-data ANNOTATIONS MANIFEST OUT` (also the first step of `train-kraken`) writes:

- `pages/<page_sha256>.{png,jpg}`: a copy of the hashed image bytes;
- `pages/<page_sha256>.xml`: PAGE XML (2019-07-15 schema) with `readingDirection="right-to-left"`. Each annotated region becomes a `TextRegion` whose `Coords` are the bounding box of its lines. Each line becomes a `TextLine` with `Coords` (polygon), `Baseline` and `TextEquiv/Unicode` in logical order. This is the input of `ketos compile -f page`; baselines and polygons make training match `blla` baseline segmentation at inference;
- `train.txt`, `validation.txt`: absolute XML paths for ketos. These stay local;
- `dataset.json`: the path-free split assignment, one row per page.

**Line polygons** (`--line-polygons`, recognition only; recorded as `line_polygons` in `dataset.json` and the record's `data`):

- `sidecar` (default): each `TextLine`'s `Coords` is the sidecar's own line polygon. R3b was trained this way, and its PAGE XML is unchanged.
- `kraken`: each line polygon is rebuilt from the gold baseline by Kraken's polygonizer, `kraken.lib.segmentation.calculate_polygonal_environment`. It runs on the grayscale page image, with the page's other baselines as boundaries and `topline` false. This is the step that turns `blla` baselines into line polygons at inference. R4a found that R3b reads sidecar-shaped polygons almost perfectly and Kraken-made ones poorly (see `docs/baselines.md`, R4a).
  - The polygonizer runs at `--polygonizer-height` (default 1800, `blla`'s input height, the scale Kraken polygonizes at during inference), and the polygons are scaled back. `0` runs it at the page's own resolution.
  - Points are rounded and clamped to the page.
  - A line the polygonizer returns no polygon for, or fewer than three distinct points, is **dropped**. If the polygonizer raises an exception on a page, all of that page's lines are dropped. Either way the run does not stop.
  - Dropped lines are counted per page (`lines_dropped_by_polygonizer` in `dataset.json`), per split, and in total (`polygonizer.dropped_lines`).
  - `polygonizer` also records `function`, `kraken_version`, `height`, `topline` and `boundaries`.
  - Kraken must be installed (`pip install 'heocr-engine[kraken]'`); without it the conversion fails before writing anything.
- `mix` (R3g): each line gets exactly one of three geometries, so the recognizer also sees crops unlike the polygonizer's.
  - **Shares:** set by `--mix-buckets`, a comma list of 1–16 geometry names (`kraken`, `sidecar`, `rect`; `kraken` required). A geometry's share is its count in the list over the list's length. The default `kraken,kraken,sidecar,rect` (R3g) gives 1/2 `kraken` (as above, at `--polygonizer-height`), 1/4 `sidecar` (the sidecar's own polygon) and 1/4 `rect`. R3h uses `kraken,kraken,kraken,kraken,kraken,kraken,sidecar,rect`: 3/4, 1/8, 1/8. A non-default list without `mix` is rejected.
  - **`rect`** is the axis-aligned bounding box of the sidecar polygon. It is padded above and below by `--rect-pad` times the box height (default 0.05, at least 1 px), clamped to the page. A negative pad, down to −0.2, trims the box instead, keeping at least 2 px. `rect` stands in for Tesseract line boxes, which on seed-101 are about 12% of the sidecar box height tighter at each edge. The box keeps the polygon's width and the gold baseline.
  - **Assignment:** `sha256("<page_sha256>\0<line_index>")`; its first 8 bytes, read as a big-endian integer, mod N, the number of buckets; the line takes the geometry of that bucket. With the default list, buckets 0–1 are `kraken`, 2 is `sidecar` and 3 is `rect`, as in R3g. `assignment` in the record spells out the rule for the list, such as `mod 8: 0-5 kraken, 6 sidecar, 7 rect`. A line's geometry depends only on its page image and index, not on the split or the input order. The split stays per sample, and validation uses the same mix.
  - **Polygonizer:** it is called only on pages with a `kraken` line, with every baseline of the page as a boundary, exactly as for `kraken`. Only `kraken` lines can be dropped, and drops are counted as above.
  - **Recorded:** `line_geometry` in `dataset.json` and the record's `data`, as `{mode: "mix", buckets, shares, assignment, rect: {source, vertical_pad}}`. Each page row in `dataset.json` adds `lines_by_geometry`, and so does each split, as `{kraken, sidecar, rect}`: kept lines, which sum to the split's `lines`.
  - A record with `mix` is invalid without `line_geometry`, with a bucket list outside the rule above, with shares or an assignment that do not follow from its list, or with per-split counts that do not sum to `lines`. So is `line_geometry` on any other mode. A record without `buckets` (R3g, made before it existed) is read as the default list.

Splits are by **sample**, so every page of a sample is on the same side. Samples are ranked by `sha256("<split_seed>\0<sample_id>")`, and the first `round(n × validation_fraction)` go to validation (at least one, never all). The result is independent of input order. ketos's own random `-p` split is not used.

## Text order

Ground truth is in Unicode logical order. Kraken 7.0.2 trains on display (left-to-right visual) order: `ketos train --reorder --base-dir R` applies the bidi algorithm to each ground-truth line. At inference, `kraken ocr --reorder --base-dir R` (`heocr-engine kraken`, default `--base-dir R`) reorders the predicted display-order line back to logical order. The two steps are inverses, so a perfect model reproduces the logical ground truth. `tests/test_training.py` checks this round trip with kraken's own functions on lines that mix Hebrew, digits, Latin and brackets. The record states both directions in `text_order`; a run whose inference direction differs from its training direction is invalid.

## Record fields

| Field | Meaning |
|---|---|
| `schema_version` | `"heocr_engine_training_run.v1"`. |
| `engine` | `{name: "heocr-engine", version}` that wrote the record. |
| `trainer` | `name` (`ketos`), `version` (from `ketos --version`), `executable_sha256`, and `kraken_version` and `kraken_executable_sha256` when `--kraken` is given (otherwise `null`). |
| `task` | `"recognition"` (a record without `task` is read as recognition), `"segmentation"` (see [Segmentation runs](#segmentation-runs)), or `"reading_order"` (see [Reading-order runs](#reading-order-runs)). |
| `init` | `"from_scratch"`: no weights are loaded (`-i`, `--load`, `--resume` and `--resize` are rejected; decision 0007). Or, for a recognizer given `--base-model` and `--base-record`, `{kind: "fine_tune", base_model_sha256, base_record_sha256, base_init, resize}`: the base record must be a valid recognition record whose `output.model_sha256` is the base model's hash, `base_init` copies its `init`, and the train command loads exactly `-i <base_model> --resize <resize>` (`union`, `new` or `fail`; `--resume` stays rejected). See decision 0013. |
| `data` | `annotation_schema`, `annotations_sha256`, `generation_manifest_sha256`; `corpora[]` as `{sha256, bytes}` for each `--corpus` text file; `split` (`unit: "sample"`, `method: "sha256_rank"`, `split_seed`, `validation_fraction`, and `assignment_sha256`, the sha256 of the canonical JSON of the per-page rows in `dataset.json`); `train` and `validation` as `{samples, pages, lines, lines_outside_logical_order, occluded_lines, pages_by_template}`; for recognition, `line_polygons` (`sidecar`, `kraken` or `mix`; absent in records made before it existed, meaning `sidecar`), and with `kraken` or `mix` the `polygonizer` object and each split's `lines_dropped_by_polygonizer`; with `mix`, also `line_geometry` and each split's `lines_by_geometry`. `lines` counts the lines written, after any drops. |
| `text_order` | `ground_truth: "logical"`, `training_reorder: true`, `base_dir`, `inference_reorder: true`, `inference_base_dir`. |
| `commands` | `compile_train`, `compile_validation` and `train` argument lists, with the ketos path replaced by `<ketos>`, the work directory by `<work>` and a fine-tune's base model by `<base_model>`. |
| `hyperparameters` | Everything passed to `ketos train`: `spec` (VGSL; the default is ketos 7.0.2's own default, passed explicitly), `batch_size`, `learning_rate`, `optimizer`, `schedule`, `quit` (`early` or `fixed`), `epochs`, `min_epochs`, `lag`, `validation_frequency`, `padding`, `augment`. |
| `run` | `seed` (ketos `-s`), `deterministic`, `device`, `precision`, `workers`, `threads`, and `environment`, the variables set for ketos that can affect training (`PYTORCH_ENABLE_MPS_FALLBACK=1` on `mps`, because PyTorch has no MPS kernel for CTC loss). |
| `outcome` | `quit`; `stopped_by` (`early_stopping`, `stopping_threshold` or `epoch_limit` as reported by the trainer log; `epoch_limit` for `quit: fixed`. ketos 7.0.2 builds Lightning's `EarlyStopping` without `verbose`, so a real run logs no stop message: the reason is then inferred by replaying that rule on `validation_history`, giving `early_stopping` when the last `lag` runs did not beat the best before them, or `epoch_limit` when `epochs` runs completed; else `unknown`); `best_epoch` (earliest retained checkpoint at the best score); `validation_runs`, and `epochs_completed` when validation runs once per epoch; `validation_metric` (`name: "val_accuracy"`, `best`, `definition`); `validation_history` (`run`, `chars`, `errors`, `val_accuracy` for every validation run, read from the ketos log because kraken 7.0.2 does not keep metrics in the converted weights); `ketos_reported_lines` and `lines_dropped_by_ketos` (lines ketos loaded versus lines converted; `null` if the log has no count). |
| `output` | `model_sha256`, `bytes`, `file_name` (bare name of `best_<score>.safetensors`), `weights_format: "safetensors"`, `byte_reproducible: false` (kraken writes random module prefixes, so a rerun does not give identical bytes). |
| `model_licence` | `status` (`"Needs verification"`, as `train-kraken` writes it, or the licence id set by a superseding decision record, e.g. `"Apache-2.0"` for R3h under decision 0010), `owner` (`maintainer`), `basis` (the decision record), `published: false` until a deposit actually happens. |

`validation_metric` is kraken's own character accuracy on the validation split, computed in display order. It selects checkpoints. It is not a hocrgen score and is not comparable to `primary.v1` numbers; report models through hocrgen.

## Running

```sh
heocr-engine train-kraken batch/line_annotations.json batch/generation_manifest.json work/ record.json \
  --ketos "$(command -v ketos)" --kraken "$(command -v kraken)" --corpus train_corpus.txt \
  --device mps --workers 0 --seed 42 --batch-size 16 --learning-rate 0.0003
```

- `work/` must be new or empty. It receives `data/`, `train.arrow`, `validation.arrow`, `checkpoints/` (ketos keeps the 10 best checkpoints) and `ketos.log`, which holds the output of every ketos step. Keep it out of the repository: it holds images and weights.
- `--timeout` applies to each ketos step (default 48 hours).
- `--workers` defaults to 0. On macOS with kraken 7.0.2, keep it at 0: with data-loader workers, ketos fails at the first epoch because worker processes are spawned and cannot pickle a local object.
- Any non-zero ketos exit fails the run and no record is written, including the Kraken 7.0.2 macOS exit-time crash (docs/baselines.md). The work directory is left for inspection.
- The trained model is used for inference with `heocr-engine kraken … --recognition-model work/checkpoints/best_<score>.safetensors`; the prediction records its sha256 as `model:recognition`, which matches `output.model_sha256`.

## Segmentation runs

`heocr-engine train-kraken-seg ANNOTATIONS MANIFEST WORK RECORD --ketos …` trains a Kraken baseline segmenter (`blla`-style) from scratch with `ketos segtrain` (decision 0008). The input, its checks and the sample-level split are the same as for recognition.

### Data

`prepare-kraken-data --task segmentation` (also the first step of `train-kraken-seg`) writes the same PAGE XML as recognition, with one change: each `TextRegion` carries its hocrsyngen region name as a kraken region type, `custom="structure {type:<region>;}"`. Region names must be 1–64 ASCII letters, digits, `_` or `-`, or conversion fails.

**Line types** (`--line-type REGION=TYPE`, repeatable, segmentation only): the lines of a mapped region carry a kraken line type, `TextLine custom="structure {type:<TYPE>;}"`. All other lines have no type, so kraken gives them the `default` line type. kraken learns and vectorizes each line type on its own output channel, so lines of different types can overlap: a stamp drawn across a body line, for example (`--line-type stamp_area=stamp`). Region names and types follow the region-name rule, and a type cannot be `default`. Without `--line-type`, every line is `default`, as before. Recognition rejects line types, and its PAGE XML never has them. `dataset.json` and the record's `data` record the map as `line_type_map` (`{}` without one), each page's sorted `line_types`, and each split's `lines_by_type`. Training fails before ketos runs if the validation split has a line type that the train split lacks.

Region geometry (`region_geometry`):

- `sidecar` when every page has the optional `regions` list (hocrsyngen S11a): `[{region_index, type, polygon, reading_order_index, line_indices}]` in `region_index` order, with an optional `region_index` on each line. Regions are written in that order with their own polygons, so a page can have several regions of one type (the three printed-letter signature blocks). The converter fails closed unless `region_index` equals the list position, the polygon is at least 3 in-page integer points, `line_indices` is non-empty and strictly increasing, every line is in exactly one region whose `type` equals the line's `region`, a line's `region_index` (if given) names that region, and `reading_order_index` is `null` or an index. `reading_order_index` is checked but not used: kraken orders regions itself at inference.
- `line_polygon_bbox` when no page has `regions`: a region is the bounding box of its lines' polygons, one per region name per page.
- A sidecar with `regions` on some pages but not others is rejected for segmentation.

Recognition output is unchanged and ignores `regions`: its PAGE XML has no region types and always uses line bounding boxes.

`dataset.json` and the record's `data` add `task: "segmentation"`, `region_geometry`, a per-page `regions` list (region types, one entry per region), and `regions_by_type` (region count per type) for each split. Training fails before ketos runs if the validation split has a region type that the train split lacks.

### What ketos 7.0.2 segtrain needs

- `-f page` with `-t train.txt -e validation.txt`, the list files from the converter. No `ketos compile` step: segtrain reads the PAGE XML and images directly.
- **No `-bl`.** With click 8.2, ketos 7.0.2 stores an explicit `-bl` as the string `'False'` in the model's `topline` metadata. kraken's segmenter then fails at inference (`KeyError: 'False'`). Without the flag, ketos stores the boolean `false`, which is the same baseline (bottom) line location. `train-kraken-seg` checks that the written model records `topline: false` and fails closed otherwise. `-tl` (topline) is not used: hocrsyngen baselines are the typographic baseline.
- **No `--resize`.** It only matters when loading a model whose classes differ from the data. A from-scratch run never loads one, and the validator rejects it.
- **mps works** (`PYTORCH_ENABLE_MPS_FALLBACK=1` is set on `mps`, as for recognition, and recorded in `run.environment`). Segtrain uses one page per batch at 1,800 pixels high; a dry run took about 0.45 s per page and epoch on an Apple-silicon mps device, including validation.

### Record fields for `task: "segmentation"`

The record has the same fields as recognition, except that `text_order` is replaced by `segmentation`:

| Field | Meaning |
|---|---|
| `segmentation` | `line_location: "baseline"`; `line_types` (the sorted train-split line types, `["default"]` without `--line-type`) and `line_type_map` (region name to line type; `{}`, or absent in records made before it existed); `region_types` (the sorted train-split region types) and `region_type_source: "hocrsyngen region name"`; `region_geometry`; `class_mapping`, copied from the trained model's metadata (`aux` separators, `baselines`, `regions` with their output indices), which must match the training data exactly; `inference`, how `heocr-engine kraken` uses the model: `command`, `segmenter` (`kraken segment -bl`), `text_direction` (`horizontal-rl`, the `heocr-engine kraken` default since decision 0009; records made before it state `horizontal-lr`, kraken's own default), `reading_order` (`polygonal_reading_order`, kraken's heuristic) and `neural_reading_order: false` (segtrain trains no reading-order head). |
| `commands` | `train` only: the `ketos … segtrain -f page …` argument list, with `<ketos>` and `<work>` placeholders. |
| `hyperparameters` | Everything passed to `ketos segtrain`: `spec` (ketos 7.0.2's default segmentation network, passed explicitly), `learning_rate`, `optimizer`, `schedule`, `weight_decay`, `quit`, `epochs`, `min_epochs`, `lag`, `validation_frequency`, `line_width` (the baseline thickness in the training target), `baseline_tolerance` (ketos `--bl-tol`, pixels, for the baseline detection metric), `dice_weight`, `augment`. |
| `outcome` | As for recognition, with the segmentation metrics. `validation_metric` is `val_mean_iu`: the mean intersection over union of the region and separator pixel classes, which ketos uses to keep checkpoints, to name `best_<score>.safetensors`, and for early stopping. `validation_history` rows hold `run`, `val_accuracy` (pixel accuracy), `val_mean_acc`, `val_mean_iu`, `val_freq_iu` (frequency-weighted IoU) and `baseline_precision`, `baseline_recall` and `baseline_f1` (ketos's baseline detection match within `baseline_tolerance`; `null` if not logged). `stopped_by` follows the same rule as recognition, replayed on `val_mean_iu`: ketos 7.0.2 builds `EarlyStopping(monitor="val_mean_iu", patience=lag)` without `verbose` here too. `ketos_listed_pages` (`train`, `validation`: pages ketos was asked to parse) and `ketos_parse_failures` (pages ketos could not parse) replace the line counts. |
| `model_licence` | As for recognition, with `basis` decision 0008. |

None of these metrics is a line-level segmentation or reading-order score, and none is a hocrgen score. Report segmenters end to end through hocrgen (`heocr-engine kraken --segmentation-model work/checkpoints/best_<score>.safetensors`), whose prediction records the model sha256 as `model:segmentation`.

```sh
heocr-engine train-kraken-seg batch/line_annotations.json batch/generation_manifest.json work/ record.json \
  --ketos "$(command -v ketos)" --kraken "$(command -v kraken)" --corpus train_corpus.txt \
  --device mps --workers 0 --seed 42 --quit early --lag 8 --min-epochs 10
```

`work/` receives `data/`, `checkpoints/` and `ketos.log`; keep it out of the repository.

### Real pages pseudo-labelled by Tesseract (R4f1)

Synthetic pages alone taught R4d to draw word-sized lines on real books. R4f adds real public-domain book scans, labelled by a local Tesseract, to the synthetic batch.

**Collecting scans** is the operator's step, outside this repository (no network code here). It writes a folder with the images and a `provenance.json` (`heocr_real_scan_provenance.v1`) that records:
- **Per file:**
  - the Commons title, URL, file page revision, sha1 (checked against a pin) and licence templates;
  - rights bases;
  - each image's page number, render URL, width, sha256 and derivation;
  - a `split` (`train` or `dev`), assigned by whole work.
- **For the folder:** the evaluation Indexes the scans exclude.

**Every page's book must be usable.** `pseudo-label-pages` and `--real-pages` both fail closed unless each used page's source:
- has a non-empty `index_key` (a Wikisource Index), or a `work_key` for other sources;
- is not one of the listed evaluation Indexes;
- has hocrgen's public-domain gate `admitted: true`.

**`heocr-engine pseudo-label-pages SCANS SCANS/real_pages.json --tesseract … --tessdata …`** runs `tesseract … -l heb --psm 3 hocr` on each scan the provenance marks for use. It writes a `heocr_real_pages.v1` manifest:
- **Lines:** Tesseract's `ocr_line`, `ocr_header`, `ocr_caption` and `ocr_textfloat` lines.
  - Each polygon is the line's own box, unpadded, because R3h is crop-sensitive.
  - Each baseline is hOCR's `baseline`, clamped to the box.
  - Lines with no words, and specks under 6 × 4 px, are dropped.
- **Regions:** each Tesseract block (`ocr_carea`) that keeps a line is a `body` region, the box around its lines plus 2 px.
- **Page filter:** geometry only.
  - The hand-free strip proxy (Otsu; long rules and frames cleared; text rows counted in 12 narrow vertical strips) must agree with Tesseract's lines crossing the same strips, at a ratio of 0.8–1.25. At least 3 lines are needed.
  - Word confidence is recorded but not used: on 19th-century prints Tesseract's recognition confidence is low even where its line finding is good.
  - Rejected pages are listed with their reason.
- **Header:** the manifest records the label source, including the Tesseract version, the `traineddata` sha256 and licence (Apache-2.0), psm and conventions. It also records the filter, the exclusions, and the scan provenance sha256.

**`train-kraken-seg … --real-pages SCANS/real_pages.json`** (and `prepare_kraken_data(real_pages=…)`):
- **Pages:** the manifest's pages are added to the split the manifest gives them, `train` or `validation`, not to the sha256-rank split.
  - Each image must match its sha256 and size.
  - Every line must sit in exactly one `body` region that contains its box.
  - The batch must have sidecar regions.
- **Template:** real pages are listed under template `real_page`. Their lines count as `lines_outside_logical_order`, because real pages have no text gold.
- **Record:** `data.real_pages` holds:
  - the manifest sha256;
  - the label source and filter;
  - the exclusions, with the full list of evaluation Indexes;
  - the files, Indexes and licence templates used, and the rejected pages counted by reason;
  - pages, lines and Indexes per split. The splits are fixed before training, by whole work, and an Index in both is rejected.

  `segmentation.region_type_source` adds `"; real pages: Tesseract blocks as body"`. The validator requires the manifest hash, the traineddata hash and licence, a non-empty exclusion list, and no evaluation Index among the pages' Indexes.

## Reading-order runs

A `ketos rotrain` reading-order model, such as A1, has no `heocr-engine` training command. It is trained with ketos directly, on PAGE XML from `prepare-kraken-data --task segmentation`. Its record is written by hand from the run's evidence, and `validate_training_run` checks it like any other record. `prepare-kraken-data` and the training commands have no `reading_order` task.

The record has the same fields as a segmentation record, with these differences:

| Field | Meaning |
|---|---|
| `reading_order` | Replaces `segmentation`. `level` (`baselines` or `regions`, ketos `--level`); `class_mapping`, the line or region classes the model was trained on, as in its metadata; `inference`, how `heocr-engine kraken` uses it: `command` (`heocr-engine kraken --api python --reading-order-model …`), `reading_order_classes` (`segmenter` or `region`), and the segmenter it was evaluated with. |
| `data` | `annotation_schema`, and `sources`: one entry per training batch, each with its own `annotations_sha256`, `generation_manifest_sha256`, `split` and per-split page counts, because the training pages may come from several batches. `corpora` lists every batch's text corpus. |
| `commands` | `train` only: the `ketos … rotrain …` argument list, with `<ketos>` and `<work>` placeholders. |
| `outcome` | As for recognition, with ketos's reading-order metric (`val_spearman`, lower is better; 0 is a perfect order on the validation pages) and `val_loss` per validation run. |
| `reconstruction` | Optional. For a record written after the run: the date, the evidence each field came from, and `not_recorded`, the fields that evidence cannot supply. Those fields hold `null` or `"unknown"` instead of a guess. |

The validator requires `task: "reading_order"`, `init: "from_scratch"`, a non-empty `data.sources` with a sha256 pin for each batch, the `reading_order` level, class mapping and inference, no weight-loading flag in the train command, and no local paths.
