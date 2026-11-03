# Stages and outside contributions

heocr-engine runs a page through `preprocess* → recognize → postcorrect*` and writes one `heocr_engine_prediction.v1` record (see [prediction_contract.md](prediction_contract.md)). Every stage that ran is listed in `pipeline[]` with its identity, licence, artifact hashes and config hash. Scoring happens in hocrgen.

There are three ways to contribute a pipeline, from least to most integration.

## 1. Predictions only

Run your system anywhere and submit one prediction file per page. Then check the files:

```sh
heocr-engine validate-predictions predictions/*.json --expect-track proprietary
```

Use `track: "open"` only when every stage is open source and network-free. Outputs from paid services, closed models or LLMs use `track: "proprietary"`: they are accepted for comparison, reported separately, and never mixed into open-track results (planning decision 0005). The validator checks:

- the schema id, which also accepts PR #1's legacy `"1.0"` files;
- that `page_id` matches `input.sha256`;
- word geometry and confidence ranges;
- track consistency across `pipeline[]`;
- that open stages declare `requires_network: false`;
- duplicate page ids;
- path-like strings in provenance fields.

It prints a JSON report with counts per track, and exits non-zero if any file is invalid.

## 2. Subprocess stage

Wrap any local program, in any language, as one stage. heocr-engine writes a JSON request to the program's stdin and reads a JSON response from its stdout:

```json
{"protocol": "heocr_engine_stage.v1", "kind": "recognize", "config": {},
 "page": {"media_type": "image/png", "width": 1200, "height": 1600, "image_base64": "..."},
 "text": "...", "words": []}
```

`text` and `words` are sent only to `postcorrect` stages. The response depends on the stage kind:

- `preprocess` returns `{"image_base64": "..."}`.
- `recognize` and `postcorrect` return `{"text": "...", "words": [...], "details": {...}}`. Only `text` is required.

Describe the stage in a manifest file:

```json
{"kind": "postcorrect", "name": "lexicon-fix", "version": "0.3.0", "license": "MIT",
 "deterministic": true, "requires_network": false}
```

Then list it in a pipeline config. Relative paths resolve against the config file's directory:

```json
{"stages": [
  {"type": "subprocess", "manifest": "deskew.json", "command": ["./deskew"]},
  {"type": "tesseract", "executable": "/opt/tesseract/bin/tesseract", "tessdata_dir": "/opt/tessdata",
   "language": "heb", "psm": 3},
  {"type": "subprocess", "manifest": "lexicon-fix.json", "command": ["python3", "fix.py"],
   "artifacts": {"script": "fix.py", "lexicon": "he.lex"}, "config": {"threshold": 0.8}}
]}
```

```sh
heocr-engine run page.png prediction.json --pipeline pipeline.json
```

The executable and every listed artifact are SHA-256 hashed into `pipeline[].artifacts`. `config` is hashed into `config_sha256`, so keep paths out of it. Commands and paths themselves are never recorded.

## 3. Python entry point

An installed package can register a factory under the `heocr_engine.stages` entry-point group:

```toml
[project.entry-points."heocr_engine.stages"]
vendor-lexicon = "vendor_pkg.stages:make_lexicon_stage"
```

The factory takes the config dict and returns an object that has an `info` attribute (`heocr_engine.stages.StageInfo`) and the method for its kind:

- `process(page) -> Page` for `preprocess`;
- `recognize(page) -> RecognitionResult` for `recognize`;
- `correct(page, result) -> RecognitionResult` for `postcorrect`.

Reference it in a pipeline config as `{"type": "entry_point", "name": "vendor-lexicon", "config": {...}}`.

## Rules and current limits

- The runner executes only stages that declare `track: "open"` and `requires_network: false`. A subprocess manifest without `requires_network` is refused. These declarations are self-attested and cannot be enforced, so run only programs you trust.
- Stages must not normalize text silently. Normalization profiles are applied explicitly by the evaluator (decision 0002). A deliberate text change is a recorded `postcorrect` stage.
- A `preprocess` stage must keep the image size. Word boxes are reported in the input frame, and geometric transforms such as crop or rotation need a coordinate mapping, which is not designed yet.
- Post-correctors may change `text` without realigning `words`. Treat words as recognizer output.
- `segment` is reserved in the contract. Recognizers that segment internally (for example Kraken) report one `recognize` stage that lists its segmentation model among its artifacts.
- To measure a preprocessing or post-correction idea, run the same recognizer with and without the stage and compare the two prediction sets in hocrgen.

## Experimental physical-line bidi projection

`heocr_engine.bidi.correct_prediction(prediction, geometry)` is a network-free,
opt-in post-correction for a narrow mixed Hebrew/Latin line-order error. It
returns `(projection, report)` and does not mutate its input. Save the original
prediction separately; the projection retains its `track`, recognizer
provenance and original `words`, and records a `postcorrect` stage when text
changes. A proprietary source stays proprietary. This is not a Unicode bidi
implementation, a reading-order model, or a claim of improved OCR accuracy.

The caller supplies prediction-side geometry in input-image pixels, with top-left
origin and `[x, y, width, height]` boxes. `geometry` has `unit: "pixel"`,
`lines` (each with physical-line `text`, `bbox`, and `words` with `text` and
`bbox`) and `tables` (objects with `bbox`). `tables: []` asserts that table
coverage was actually checked and none were detected; omitted metadata is not
an empty detection. Coordinates must be finite and in the input frame. A caller
must not derive this metadata from evaluation references. Current built-in
recognizers do not provide this complete contract. Missing or malformed geometry
returns the unchanged prediction with an explicit abstention report.

Only unique matches of one physical line are considered. The stage requires
matching token multisets, Hebrew and Latin, disjoint horizontally ordered word
boxes within one pixel of the line box, and no table intersection, digits,
finite-list negation or adjacent Latin words. Overlapping candidate matches
abstain. It does not establish that a line outside detected tables is safe, nor
protect against negations outside the finite list. It joins changed tokens with
single spaces. Measure it against a raw baseline, report changes and abstentions,
keep synthetic and real results separate, and inspect semantic regressions.
The one-pixel tolerance was chosen after a small development evaluation, not
preregistered; development pages are not a holdout.
