# Modern Hebrew handwriting contribution campaign

Proposed pilot for [handwriting v1](handwriting-v1.md). Collect **2,000–5,000 verified lines from at least 50 writers**, roughly 40–100 accepted lines per writer at 50 writers. Invite people with a range of everyday Hebrew cursive styles and ask for a few pages each. Count accepted lines after writer, photo and transcription checks.

## What volunteers do

1. Copy an assigned sheet of plain, unpointed Hebrew lines from a pinned `htext-cc0` release. Select short passage lines with enough room to finish each on one line. Vary vocabulary, line length and ordinary punctuation. Keep the prompt ID with the submission through the intake form. [HeOCR/htext](https://github.com/HeOCR/htext) · [CC0 data licence](https://github.com/HeOCR/htext/blob/main/LICENSE-DATA)
2. Write in your usual handwriting, with a pen or pencil on blank or ruled paper. Copy one prompt per line and leave space between lines. Submit only pages you wrote yourself. Keep names, signatures, phone numbers and other personal information off the page and out of the frame.
3. Photograph each full page separately, flat and right side up. Use even light, hold the camera parallel to the page, keep all corners in frame and check that the writing is sharp. Upload the photo with its prompt ID. Skip and retake anything blurred, cropped or obscured.

## Consent and intake

Before upload, ask volunteers to confirm that they wrote and photographed the pages themselves and agree to dedicate their own submitted handwriting and photos to the public domain under **CC0 1.0**. Tell them that accepted assets and transcripts may be published in an open dataset and used for model training, including commercially. Show the release terms before submission and record affirmative consent with its version. Screen photos for personal details and strip EXIF/location metadata before release. Keep contact, consent and writer matching records private. [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/)

The review app's approved terms `2026-11-18-v1` cover reviewers' decisions and text they edit or type from scans under CC0 1.0. Use those terms for line transcription. The maintainer should approve separate intake wording for the submitted handwriting and images before the campaign opens. The source prompts retain their existing rights. [Handwriting terms decision](https://github.com/HeOCR/heocr-review/blob/main/docs/decisions/2026-11-18-terms-handwriting.md) · [CC0 scope decision](https://github.com/HeOCR/heocr-review/blob/main/docs/decisions/2026-11-12-cc0.md)

The lead supplies the private protected-writer list. Assign a stable internal key to each writer and resolve repeat submissions and aliases. **Exclude every contribution from any protected benchmark writer.** Keep submissions with unresolved writer identity or overlap out of training and development. Split eligible material by writer before use, keeping all pages and lines from a writer together. Keep the protected list and writer keys out of public artifacts.

Use the prompts to assist verification. Check each crop against what was actually written and have an independent reviewer adjudicate differences or illegible lines. Count verified photo-and-text pairs and distinct eligible writers toward the target.
