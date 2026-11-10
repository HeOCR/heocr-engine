# 0014 — Every trained model is released openly; no licence-tainted inputs

- Status: accepted
- Date: 2026-11-10
- Decided by: the maintainer (Shay Palachy Affek), 2026-11-10; written by the HeOCR team lead
- Supersedes:
  - decision 0007's and decision 0008's "No publication" clauses;
  - decision 0010's item 8 (a separate go-ahead for each publishing action), which also applies to R4d and A1 through decision 0011;
  - decision 0013's "Publishing any of them is the maintainer's call".

## Context

Until now, trained weights were unpublished by default, and each publishing step needed the maintainer's go-ahead. On 2026-11-10 the maintainer reversed this, in his words: "הכל פתוח. כל משקל. תמיד. זו ההחלטה תמיד. זה הכלל. הכלל הקיים שמבקש אישור שלי הוא טעות". (Everything is open. Every weight. Always. That is the decision, always. That is the rule. The existing rule asking for my approval is a mistake.)

In the same message he set a rule for the supply chain. No resource may enter the training pipeline if its licence would later cast doubt on releasing the derived data or models openly. Attribution and share-alike terms, such as CC BY or CC BY-SA, are acceptable. If an existing model was trained with a font whose licence is problematic, the model is discarded.

## Decision

1. **Open by default, always.** Every trained model's weights are released openly, together with its card, NOTICE, LICENSE and training record. No per-model or per-step approval is needed.
2. **Licence-clean inputs only.** Every input of a trained model must have a licence that allows open release of the result. Inputs include fonts, scans, texts, glyph banks and starting weights. These are out:
   - non-commercial terms;
   - no-derivatives terms;
   - "personal use" terms;
   - proprietary or OS-bundled fonts;
   - no licence, or an unknown one.

   An input whose licence is not known stays out of the pipeline until it is known.
3. **Attribution and share-alike are carried.** A CC BY or CC BY-SA input is credited in the model's NOTICE. Where a share-alike term reaches the weights, it is applied to them. The BiblIA_01 question in decision 0006 stays open, and BiblIA_01 is not a starting point (decision 0007).
4. **Tainted models are discarded.** A model is discarded, not released, when any of its inputs fails item 2. Its record keeps the reason.
5. **Where releases go:**
   - the Hugging Face organisation `HeOCR`, where R3h, R4d and A1 already are;
   - Zenodo, with a version DOI.

   Credentials come only from the environment. No account is created by an agent.

## Consequences

- `published: false` in training records means "not yet released". It no longer means "held back". The release step is part of finishing a model.
- Licence evidence is recorded in the training record before training starts, for every input, so that item 2 is checked at the start and not at release.
- An audit of the fonts used by the existing models is under way (2026-11-10). Any model it marks as tainted is discarded under item 4.
- Eval rules are unchanged. Decision 0012's scored sets are still never tuned or selected on, and released training data still holds out whole eval works.
