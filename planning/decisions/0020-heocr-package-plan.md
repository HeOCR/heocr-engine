# 0020 — The `heocr` package: name, licences, external tools, Adanim code, team and VLMs

- Status: accepted
- Date: 2026-11-16
- Decided by: the maintainer (Shay Palachy Affek), 2026-11-16, in the heocr-lead session, deciding each open item of the proposal [`document-pipeline-package.md`](../proposals/document-pipeline-package.md) §9; written by `lead[claude/claude-code#shay-macbook-m4]@heocr/opensource`
- Serves: decision 0019, the top goal
- Accepts: the proposal as the plan for the package, with the choices below. Where the proposal and this record differ, this record wins.

## Decision

1. **Name and home.**
   - The package is `heocr` on PyPI.
   - It lives in a new repository, `HeOCR/heocr`, under Apache-2.0. The PyPI and import name is `heocr` too.
   - **Repository name (2026-11-16):** GitHub repository names are case-insensitive, and the public dataset release repository `HeOCR/HeOCR` held the name. The lead first used `HeOCR/heocr-py` instead. The same day, the maintainer decided to rename the dataset repository to `HeOCR/heocr-datasets` and give the package `HeOCR/heocr`, its chosen name.
   - heocr-engine stays the research runtime for training and evaluating models. The package uses the models heocr-engine releases.
2. **Copyleft only as an optional extra.**
   - The core and its default install have permissive dependencies only.
   - A copyleft library may come in as an optional extra that the user installs on purpose, for example `heocr[mupdf]` for PyMuPDF (AGPL-3.0).
   - The extra's documentation must say plainly that installing it brings that library's licence terms.
   - No default route may require an extra.
   - Copyleft tools may also run as benchmark baselines.
3. **External programs are optional and never bundled.**
   - Tesseract and LibreOffice are used when the user has installed them.
   - Without them the core still runs. For each page or file, it records which route was unavailable.
4. **Adanim code.**
   - **The volunteer's repository** (`AdanimInstitute/social-procurement-yonatan-amster-project`) is released for reuse. The maintainer adds its licence file.
   - **The production tender pipeline** (`AdanimInstitute/adanim-govil-scraper`, `tendex_l4/`) may have specific pieces ported into `heocr` under Apache-2.0, credited in the commit that ports them. The pieces:
     - file-type identification;
     - the text-layer warning flags;
     - right-to-left line building;
     - the rule for when an alternative reading order is safe to use.

     Ported pieces come without the PyMuPDF dependency. This is not a release of the whole package.
5. **Real government documents.**
   - They form a private internal corpus, used for internal evaluation only.
   - The corpus is never published and never used for training.
   - It is kept with HeOCR's restricted evaluation material.
6. **Team.**
   - A new role, `pipeline[claude/claude-code#shay-macbook-m4]@heocr/opensource`, builds `heocr` in its own session.
   - The lead reviews and merges its PRs; no author merges their own (decision 0001).
   - Evaluation (`eval[…]`) builds D-bench, per decision 0017.
7. **Vision-language models already in v1, as an optional route.**
   - The route is off by default.
   - It is used only for hard pages, meaning pages or regions the other routes could not read.
   - Decision 0014 still applies to it. Only models whose weights allow open use can be in the route, and no model is bundled.
   - The lead adds two safeguards to the design, which the maintainer can change:
     - every word the model writes is checked against the page's text layer where one exists;
     - the route's output is marked `vlm: unverified`.

## Consequences

- **Next step:** open the `pipeline` session and the `HeOCR/heocr` repository. D1, as defined in the proposal, comes first.
- **Evaluation:** eval gets D-bench as a task. It also gets the internal corpus, which goes into the restricted evaluation material.
- **The VLM route** is planned in D2, after the other routes exist, so that hard pages are defined by their failure.
