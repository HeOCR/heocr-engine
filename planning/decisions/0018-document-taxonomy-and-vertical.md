# 0018 — A hierarchy of Hebrew document sets; new printed is the vertical

- Status: accepted
- Date: 2026-11-11
- Decided by: the maintainer (Shay Palachy Affek), 2026-11-11, in the heocr-lead session (a drawn taxonomy, plus the instructions quoted below); written by `lead[claude/claude-code#shay-macbook-m4]@heocr/opensource`
- Owner of the evaluation side: `eval[claude/claude-code#shay-macbook-m4]@heocr/opensource`
- Amends: decision 0017. Its three flat domains (H, P-hist, P-mod) become nodes of this tree. Its niqqud stratum, its four measures and its rights and privacy rules stand.

## The tree

```text
hebrew
├── printed
│   ├── new printed (~1908 and later)
│   │   ├── by genre: books · newspapers · laws and government documents · etc.
│   │   └── by font: modern sans-serif (Arial, Narkisim, Chaim, Miriam, …) · modern serif (Frank Rühl, David, Hadassah, …)
│   └── old printed (~before 1908)
├── modern mixed
│   └── filled-out forms
└── handwritten
    ├── new handwritten (~1920 and later)
    └── old handwritten (~before 1920)
        ├── Ashkenazi cursive (רהוט אשכנזי)
        └── Sephardi cursive (רהוט ספרדי)
```

## Decision

1. **Placement uses heuristics, not a date rule.** The maintainer: "don't make the year a rule! ... it's a thought; a suggestion; a heuristic; fonts can also guide us, as well as genres".
   - A unit (a book, document series or writer) is placed by weighing several signals: typography and letterforms, genre, and approximate date.
   - **One genre rule is firm:** rabbinic, Torah and other holy texts are **always old printed**, whatever their print date or typeface.
   - When the signals disagree or are unclear, the unit stays **unclassified**, and a human decides from the scan. An agent may propose a node, but never fixes an unclear one.
   - **A fuller definition is pending.** A deep-research consultation on Hebrew typographic history and document genres, commissioned by the maintainer on 2026-11-11, will feed it. Until then, these heuristics apply.
2. **Selectable sets, with a score for every model.** A person can pick any node down to at least the second level below *hebrew*:
   - printed → new printed, old printed;
   - modern mixed → filled-out forms;
   - handwritten → new handwritten, old handwritten.

   For that set they can see how each HeOCR model performs, with 0017's measures (character, word, line, page) and intervals.
3. **A dedicated model per set.** Each selectable set is meant to get a model chosen for it. The model card names its set.
4. **The vertical now is new printed.** It is the maintainer's own use. Until it is good enough:
   - **Evaluation:** test and eval sets focus on new printed, and its genre and font facets are reported under it.
   - **Selection:** checkpoint and model selection uses new-printed dev only.
   - **Other sets are training parameters:** old printed, rabbinic, handwriting and so on enter a training mix only if they improve new-printed dev, and they are left out if they do not.
5. **Later aggregates state their weights.** When the work expands, first to all printed and then to all Hebrew, an aggregate score must state the weight or ratio of each subset it averages. A blended number with no stated weights is never reported.
6. **Font facets are labels of real documents.** "Modern sans" and "modern serif" classify the typefaces seen in real scans. Using a named font to make synthetic data still follows the iron rule of decision 0014: only fonts whose licence allows open release, for example the OFL "Libre" versions.

## Consequences

- **From 0017's domains to the tree:**
  - P-mod is new printed (laws and government documents, plus other modern genres) together with modern mixed (filled-out forms).
  - 0017's P-hist/standard-square units are new-printed books wherever their typography is modern.
  - Rabbinic, Torah and holy texts are old printed (the firm genre rule), and so is other old-style print.
- **audit2 pages:** they are reclassified by look, per unit. Its new-printed pages give new printed a scored set today.
- **R8:** it is selected on new-printed dev only. The rabbinic line sets (rablines_v1, wslines_v1) are enrichment candidates, kept only if new-printed dev improves.
