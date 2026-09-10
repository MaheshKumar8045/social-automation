# Social Automation — Project Checkpoint

## Goal
Build a source-grounded book/PDF-to-visual-generation knowledge pipeline. The downstream generator must produce visually coherent scenes and frame-to-frame character/object/environment continuity. Unknown source information must remain unknown rather than being invented.

## Environment
- Local project: `M:\social-automation`
- Python: 3.13.15
- Windows PowerShell
- Virtual environment: `.venv`
- Git branch: `main`
- GitHub repo: `MaheshKumar8045/social-automation`
- Real validation PDF: `data\Asura\Asura - Tale Of The Vanquished.pdf`

## Current verified baseline
The one-command DoD pipeline has been exercised against the real Asura PDF and completed successfully before the latest fixes:

```text
pages:        442
sections:     15
scenes:       184
QA:           passed under the previous structural validator
```

The real run exposed two classes of issues that are now being addressed:
1. structural section detection dropped chapters 1 and 2 even though Docling detected them;
2. the prompt QA was structurally correct but too weak to represent a production-quality gate.

## Important correction about the prompt inspection
A previous inspection script looked for the wrong top-level keys and therefore incorrectly reported that characters, short-video prompts, long-video prompts, and audio were empty.

The current `GenerationPlanner` already produces:

- `characters`
- `image_prompt`
- `short_video_prompt_package`
- `long_video_prompt_package`
- `audio_prompt`
- `media_prompt_package`
- `source_evidence`

The current `Prompt Export` layer reads those same fields. Therefore the earlier A/B question is resolved: **this was not an exporter field-name mismatch and the planner does create the media packages.** The remaining work is quality/grounding validation, not wiring those fields into existence.

## Structural detection investigation
Docling was directly verified to classify the real chapter openers as `section_header`:

```text
PDF page 11 -> 1 The end
PDF page 16 -> 2 THE SEED
PDF page 21 -> 3 Captives
```

The scanner regex also matches all three.

The failure was downstream because the generic layout detector was being combined with explicit Docling `section_header` candidates before page classification. The scanner could therefore allow generic candidates to affect the contents-page heuristic.

### Fix committed
`core/docling_structure_scanner.py` now gives a **single numbered Docling `section_header` candidate precedence** over generic layout candidates on that page. Multiple Docling candidates still go through the normal contents-page protection logic.

A regression-testable `_select_candidates()` helper was added.

Relevant commits:

- `cc8e5312721891f2ba7feaaf206d033fe627b52c2` — Fix Docling section-header precedence
- `85629123f4136ac118db52b0b25c9cbad1142a7d` — Make Docling candidate precedence testable
- `2aa321dc24f97d1274944d730b173d28395db019` — Add Docling heading precedence regression test

### Required verification
Run the real scanner/DoD again and confirm that pages 11 and 16 become sections. Do not assume the expected final count until the real PDF is rerun.

## Prompt / media planning
`core/generation_planner.py` is the canonical plan builder and delegates to `core/media_prompt_compiler.py`.

The canonical media package has three primary generation outputs:

```text
image
short_video
long_video
```

Audio is supporting material inside the video packages and is also exposed as `audio_prompt` for compatibility.

The compiler already creates:
- image prompt
- short-video clips
- long-video shots
- dialogue source / overlays
- music direction
- sound-design direction
- continuity and unknown-preservation constraints

## Prompt QA improvements
`core/prompt_export.py` was strengthened so DOD no longer checks only for the existence of fields.

It now verifies:
- minimum production length for the image prompt;
- explicit source-grounding language;
- short-video clip count and numbering;
- minimum prompt length for each clip;
- long-video shot numbering and minimum prompt length;
- nonempty music direction and sound design;
- unified `media_prompt_package` structure and grounding flags;
- source evidence presence;
- if canonical characters exist, at least one canonical character name must reach the image prompt.

Regression tests were added in `tests/test_prompt_export.py`.

Commit:

- `a6ce85471419fbfdcc6301dbf04f3f1fcbb7216d` — Strengthen prompt package QA
- `df9d92de2c68f69db14c91bec023e9f8404f2a87` — Add prompt package QA regression tests

## Prompt compiler cleanup
`core/generation_prompt.py` previously contained hardcoded book-specific extraction rules such as specific locations and dates. That created a dangerous second source of truth for a generic book pipeline.

It has now been converted into a compatibility wrapper around the canonical media compiler. It contains no book-specific chapter/location logic.

Commit:

- `64b967f691e0ce8f2bae66d12e395d5d37f4cada` — Remove book-specific prompt compiler logic

## Character pipeline
The character pipeline remains deliberately conservative:

- candidate gate
- character evidence classification
- identity normalization
- identity evidence
- mention identity resolution
- canonicalization

Do not loosen the character gate without a demonstrated false-negative/false-positive regression.

## Visual Knowledge Bible
Canonical visual facts must remain source-supported. Generated guidance is never evidence. Unknown visual attributes remain unknown.

The visual layer must remain connected to canonical characters rather than all raw entity candidates.

## Continuity
Continuity tracks character presence, visual state, persistent objects, environment state, and scene-to-scene changes. Canonical identity must not be overwritten by scene-specific state.

## Generation architecture
Canonical path:

```text
Generation Context
  -> Generation Planner
  -> Unified Media Prompt Compiler
  -> Image / Short Video / Long Video packages
  -> Provider abstraction
  -> Generation queue / production
```

Do not add another prompt-building layer unless an existing component is first shown to be insufficient.

## Production-readiness rule
A passing structural DoD is **not** sufficient evidence that prompts are production-ready. Future DoD work must validate both:

1. structural completeness;
2. minimum media-prompt quality and grounding contracts.

The deterministic compiler is intentionally conservative. It must not hallucinate appearance, actions, dialogue, setting, or progression merely to make a prompt sound cinematic.

## OCR quality rule
OCR artifacts such as malformed words must not be silently converted into invented source facts. If OCR quality is insufficient, the system should preserve uncertainty or fail a quality gate rather than fabricate a correction.

For digitally-born PDFs, native PDF text extraction may provide better character fidelity than OCR; for scanned PDFs, OCR remains necessary. Any future text-quality improvement must be validated against actual source pages before becoming canonical.

## Current next steps
1. Pull latest `main`.
2. Run the full pytest suite and record the new count.
3. Run the real Asura DoD pipeline again.
4. Verify chapters 1, 2, and 3 are all structural sections.
5. Inspect a few generated plans using the correct keys listed above.
6. Confirm the strengthened QA behaves as intended.
7. Only after these pass, improve semantic scene segmentation / OCR quality and then evaluate providers.

## Resume rule
Current Git `main` code and newly verified behavior take precedence over older milestone notes. Do not repeat the earlier mistaken conclusion that the video/audio fields are empty without inspecting the canonical nested plan keys.
