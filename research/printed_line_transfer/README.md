# R3e: Bounded printed-line transfer diagnostic

This is a small offline research receipt, not a production trainer, a public
model release, or a real-document benchmark. The existing R3b recognizer is
loaded locally and fine-tuned on newly authored synthetic lines. Original and
tuned models are then compared on exactly the same held-out synthetic line
images. Crops use generator-supplied line geometry: this measures recognition,
not segmentation or page reading order.

Use hocrsyngen source commit `1ad83aabc00b657224bbeb8ec2814a1c8ceb2940`
(the plain-evaluation composition), ketos/Kraken 7.0.2 and the source-approved
R3b weights supplied locally. The recorded base-model SHA-256 is
`0b5a0c3c0d66599095068f94234e86f563e17182a34b863d7e4941ef54b9e362`.
That model was originally trained from scratch on Alef and Gveret; prior
exposure beyond its recorded inputs is unknown. Decision 0007 keeps its license
**Needs verification** and does not authorize publishing weights. Alef and
Noto Sans Hebrew are separately OFL 1.1 fonts: obtain licensed local copies.
The evaluated Noto variable-font SHA-256 is
`838341dcb5c33b3160dc6077637049fd9c49564323215e1e2754d6754bb1a463`.

The authored groups are disjoint as exact strings, but share vocabulary and
syntactic templates. Train and validation use Alef, with separate text groups;
test uses Noto plus separate text. Noto was not among the fonts documented in
the base R3b run. Inputs are simple generated sentences, no dates or negation,
and are not a representative public-document corpus. Do not use this dataset
to tune a claim about real OCR accuracy. Freeze hashes and examine sample text
against image pixels before training; geometry flags do not certify labels.

Run from the repository root with a Python environment containing Pillow with
libraqm, ketos/Kraken 7.0.2 and dependencies, providing all paths explicitly:

```sh
python research/printed_line_transfer/setup.py --output OUT --alef-font ALEF_TTF --noto-font NOTO_TTF
python research/printed_line_transfer/prepare.py --output OUT --generator-src HOCRSYNGEN_SRC
python research/printed_line_transfer/pagexml.py --output OUT
python research/printed_line_transfer/train.py --output OUT --base-model BASE_MODEL --ketos KETOS
python research/printed_line_transfer/evaluate.py --output OUT --base-model BASE_MODEL --kraken KRAKEN
```

`HOCRSYNGEN_SRC` is the checkout's `src/` directory. Output must be a new
local directory outside this repository. No tool downloads a model, and no private source material is
needed. This deliberately uses hocrsyngen's private generation helper to test a
locally supplied Noto font: its Noto manifest is an experimental font override,
not a canonical hocrsyngen-governed batch. The preparation sidecars and image
hashes identify the actual local inputs. Check corpus, font, image and label
hashes before training; keep test text and font fixed before model selection.
The trainer uses CPU, four threads, two fixed epochs, 900 seconds and 1 GiB of
checkpoint output as limits; only validation determines the saved best model.
PAGE XML is necessary because the installed ketos 7.0.2 `train -f path` claims
to accept path data but fails before training. The first failed attempt took six
seconds and produced no model.

Recorded run: 24/8/12 pages and 92/25/36 retained train/validation/test body
lines, with 4/7/12 flagged lines excluded respectively. The retained sets contain
62/17/24 unique strings. Crops were rescaled to 0.8, 1.0 and 1.2; only nine
sample images were visually checked, not all labels. The two-epoch run took
71.33 seconds and produced about 113 MB of checkpoints; epoch 0 was selected
on validation (a tie at 0.9980 character accuracy). Both model evaluations
returned 36/36 outputs. Raw Unicode code-point edits were 275/1,397 base and
269/1,397 tuned; raw whitespace-token word edits were 171/222 and 169/222.
The small difference on correlated synthetic material is not evidence of a
meaningful improvement, and raw line WER of roughly 77% remains high. The
Kraken test command also reported normalized character and word accuracy; the
raw comparison is the primary figure. No real-source images, references,
weights, predictions or sensitive payloads are included here.

Model fitting is not bitwise deterministic across environments. CPU model,
Pillow/font rendering and exact dependencies can change assets, checkpoints and
scores. Stop on missing/failed output and retain the full denominator; do not
silently substitute a different font, selection or model.
