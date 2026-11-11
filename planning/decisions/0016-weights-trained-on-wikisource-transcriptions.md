# 0016 — Weights trained on Hebrew Wikisource transcriptions of public-domain works stay Apache-2.0, with attribution

- Status: accepted
- Date: 2026-11-11
- Decided by: the maintainer (Shay Palachy Affek), 2026-11-11, answering in the heocr-synth-gen session ("Apache + attribution"), relayed to the team lead; written by the HeOCR team lead
- Builds on: decisions 0014 and 0015

## Context

R8 adds Hebrew Wikisource proofread page text as training labels (`wslines_v1`), to cover rabbinic and dense small-type prints. That text is licensed CC BY-SA 4.0. The question was: "Which licence should R8's weights take if they train on Wikisource text?" The options were Apache-2.0 with attribution, or CC BY-SA 4.0 weights.

Before deciding, the maintainer saw this reasoning:
- **The weights are probably not "Adapted Material" under CC BY-SA 4.0.** A Tesseract LSTM stores letter shapes. R6 and R7 also kept tessdata_best's word list, so no Wikisource text is in the `traineddata`.
- **Training needs no permission** under Israel's Ministry of Justice fair-use opinion (December 2022), the 2025 US fair-use rulings, or the EU text-and-data-mining exceptions.
- **A faithful transcription of a public-domain work has thin copyright.**
- **Precedent:** BERT and T5 (Apache-2.0) and RoBERTa (MIT) were trained on Wikipedia.
- **Risk:** the law is unsettled.

## Decision

1. **Weights stay Apache-2.0.** Weights trained on Hebrew Wikisource proofread transcriptions of public-domain works (CC BY-SA 4.0) are released under Apache-2.0, as in decision 0014.
2. **Credit the text as a training source.** The NOTICE and card credit "Hebrew Wikisource contributors" (CC BY-SA 4.0) as a source of training text, not only of scoring references, and name the line set and its per-page permalinks.
3. **Keep the label text out of the `traineddata`.** No word list or dawg is built from Wikisource text. The starter keeps the base word list, so the weights argument in the context holds.
4. **Published labels follow their licence.** If a line set with Wikisource labels is published, its label text carries CC BY-SA 4.0 with attribution, which is an exception to "CC0 data" limited to that text. Scan crops and HeOCR's own metadata are unaffected.
5. **Scope.** This decision covers Hebrew Wikisource proofread transcriptions of public-domain works only. The thin-copyright argument holds for faithful transcriptions of PD works, not for original works. Other CC BY or CC BY-SA text sources (for example Sefaria versions) need their own decision. Non-commercial and no-derivatives text stays excluded (the iron rule of decision 0014).
