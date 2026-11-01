# HeOCR Engine

A small local OCR baseline for PNG and JPEG pages using an independently installed Tesseract and its language models. No network access, model download, or paid service is used by the program. Python 3.11+, Pillow, and a POSIX system are required; Windows is not supported by this baseline. Install dependencies separately in your environment and run `pip install .`.

```sh
heocr-engine page.png prediction.json --executable /path/to/tesseract --tessdata-dir /path/to/tessdata
```

The default is `--language heb --psm 3`; use e.g. `--language heb+eng` for a mixed-script model set, and `--timeout 60` to set the deadline in seconds for each Tesseract call. Supply a trusted, pinned local executable and traineddata files. The program records their SHA-256 hashes and the Tesseract version; it does not verify these against an external registry. These hashes aid provenance but do not guarantee identical results across machines, libraries, or execution environments. The output file must not already exist. PSM modes 0, 1, and 12 use the additional OSD model and are rejected so that all loaded models are recorded. PSM 2 is also rejected because it does not produce OCR text. Input is limited to 50 MB and 40 million pixels. TIFF, PDF, animation, and remote inputs are unsupported.

## Prediction contract

Each run writes one `heocr_engine_prediction.v1` JSON object per page; see [docs/prediction_contract.md](docs/prediction_contract.md). `page_id` is `sha256:` plus the image file's SHA-256, and `engine` records the Tesseract version, executable hash, ordered language/model hashes, and page segmentation mode. No source, executable, model, or temporary path is recorded. `text` is the unmodified UTF-8 text produced by Tesseract; no RTL reversal or normalization is performed. `words` follows Tesseract TSV order without sorting. Degenerate (zero-area) boxes are preserved and marked. Invalid images, missing model/output files, failed calls, timeouts, invalid coordinates, and invalid confidence values fail the run. Avoid putting sensitive text in publicly shared predictions.

## Kraken baseline

`heocr-engine kraken IMAGE OUT --executable … --segmentation-model … --recognition-model …` runs an installed kraken with local models. See [docs/baselines.md](docs/baselines.md) for the reference models and their licences.

## Pipelines and outside contributions

`heocr-engine run IMAGE OUTPUT --pipeline pipeline.json` composes preprocess, recognize and post-correct stages, which can be local subprocesses or installed Python entry points. `heocr-engine validate-predictions FILE...` checks prediction files submitted from elsewhere, including `track: proprietary` outputs, which are reported separately. See [docs/stages.md](docs/stages.md). `heocr-engine tesseract ...` is the same as the original command.

## Planning

Roadmap, notation and decision records live in [planning/](planning/README.md). Scoring stays in hocrgen; this repository produces predictions.

Run offline tests with `python -m unittest discover -s tests`. The tests use generated synthetic pixels and a mocked backend; they make no OCR accuracy claim.
