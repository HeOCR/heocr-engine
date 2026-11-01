# HeOCR Engine

A small local OCR baseline for PNG and JPEG pages using an independently installed Tesseract and its language models. No network access, model download, or paid service is used by the program. Python 3.11+, Pillow, and a POSIX system are required; Windows is not supported by this baseline. Install dependencies separately in your environment and run `pip install .`.

```sh
heocr-engine page.png prediction.json --executable /path/to/tesseract --tessdata-dir /path/to/tessdata
```

The default is `--language heb --psm 3`; use e.g. `--language heb+eng` for a mixed-script model set, and `--timeout 60` to set the deadline in seconds for each Tesseract call. Supply a trusted, pinned local executable and traineddata files. The program records their SHA-256 hashes and the Tesseract version; it does not verify these against an external registry. These hashes aid provenance but do not guarantee identical results across machines, libraries, or execution environments. The output file must not already exist. PSM modes 0, 1, and 12 use the additional OSD model and are rejected so that all loaded models are recorded. PSM 2 is also rejected because it does not produce OCR text. Input is limited to 50 MB and 40 million pixels. TIFF, PDF, animation, and remote inputs are unsupported.

## Prediction contract

One JSON object per page, `schema_version: "1.0"`. `page_id` is `sha256:` plus the image file's SHA-256; the `input` object records that hash and pixel dimensions. `engine` records the Tesseract version, executable hash, ordered language/model hashes, and page segmentation mode. No source, executable, model, or temporary path is recorded. `text` is the unmodified UTF-8 text produced by Tesseract. It is expected to be Unicode logical order; no RTL reversal or normalization is performed. `words` follows Tesseract TSV order without sorting, each containing the unmodified word, confidence on Tesseract's 0–100 scale, and `[x, y, width, height]` in pixels, with origin at the top left and right/bottom edges exclusive. `geometry_status` is `valid` for positive-area boxes and `degenerate` when Tesseract reports zero width or height. Degenerate boxes are preserved exactly and do not define a usable crop. This schema is not a statement of reading-order correctness or OCR accuracy. A consumer should explicitly map content-derived page IDs to its own dataset IDs.

Text and word lists are separate Tesseract outputs and need not align exactly. Invalid images, missing model/output files, failed calls, timeouts, invalid coordinates, and invalid confidence values fail the run. Avoid putting sensitive text in publicly shared predictions.

Run offline tests with `python -m unittest discover -s tests`. The tests use generated synthetic pixels and a mocked backend; they make no OCR accuracy claim.
