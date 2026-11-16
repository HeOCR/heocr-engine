# 0019 — HeOCR's top goal is a document pipeline: the best open way to get Hebrew text out of any document

- Status: accepted
- Date: 2026-11-16
- Decided by: the maintainer (Shay Palachy Affek), 2026-11-16, in the heocr-lead session; written by `lead[claude/claude-code#shay-macbook-m4]@heocr/opensource`
- Relation to earlier decisions: this record sits above all of them. It changes no earlier outcome. Decisions 0017 and 0018 (evaluation per document set; new printed is the vertical) and decisions 0014 and 0015 (open release; licences of training inputs) stand.

## Context

In November 2026, a pipeline built outside HeOCR for transcribing government tender documents was run on 132 Israeli government documents. The documents were born-digital PDF, scanned PDF, DOCX, DOC and HTML files. A comparison with off-the-shelf tools found:

- it was better on PDFs whose text exists only as an image;
- it was worse on PDFs with a text layer (except for tables) and on Word files.

So the best result came from different tools for different kinds of input, and no single engine won. The maintainer drew the conclusion that the project's product should be the routing, not one model:

> "I want HeOCR, in the end, to have a simple Python package that provides a pipeline, not a model, that is the best for extracting Hebrew from all kinds of documents, period." (translated from Hebrew)

## Decision

1. **The top goal.** HeOCR's top goal is a simple Python package that, given any document, returns its Hebrew text through the best pipeline available for that kind of document.
   - The deliverable is the pipeline, not a model.
   - "Any document" includes born-digital PDF, scanned PDF, PDFs that mix the two, Word files (DOCX and DOC), images, and other common office and web formats.
2. **Automatic routing.** The package detects what kind of document, page and region it has, and uses the right tool for each.
   - This includes the different levels and forms of text encoding inside a PDF: a correct text layer, a text layer in visual order, broken font mappings, a garbage text layer from a foreign OCR, image-only pages, and text drawn as images or vector paths.
   - The user does not have to know which case they have.
3. **Open-source tools, ours where we can.** The pipeline uses whatever open-source tools give the best result.
   - Where a tool is needed, HeOCR code that does the job as well or better is preferred to adding another dependency.
   - A dependency is acceptable when it is needed.
4. **Models are a means.** HeOCR's recognizers and segmenters are a means to this goal, and there is still room to improve them. They are judged by how much they improve the pipeline on the inputs where OCR is the right route.
5. **Rules that still apply.**
   - **Licences:** every component, model and weight the package ships or downloads follows decision 0014's iron rule. Components with non-commercial or field-of-use restricted weights are out of the default pipeline.
   - **Evaluation:** evaluation per document set follows decisions 0017 and 0018.

## Consequences

- **Planning:** a proposal for the package (its name, the routing stages, the first supported formats, and a document-level benchmark across formats) comes next, for the maintainer's decision. It does not exist yet.
- **Evaluation:** HeOCR will need document-level evaluation beside the page and line sets. That includes cases where the right answer is not OCR, such as text-layer PDFs and Word files.
- **Existing work:** the new-printed vertical (decision 0018) and the model work continue. They now feed the image route of the pipeline.
