## Visual generation policy upgrade — 2026-09-11

Implemented locally by this upgrade script:

- Source-supported visual facts and production inference are now separated by provenance.
- Controlled inference is deterministic and genre-configurable; source facts always override it.
- Mythological-epic priors provide broad missing production details without inventing exact eye color, hair color, height, exact age, or facial measurements.
- Canonical characters receive stable visual identity anchors and locked inferred attributes for cross-scene continuity.
- Primary media composition is mobile-first 9:16, with explicit safe-area, subject-scale, background-share, and dialogue-box rules.
- Images require at least one dialogue-or-narrative box; source dialogue is preserved when present, otherwise the source scene title is used as a non-spoken narrative box so the system never fabricates speech.
- Prompt compilation now selects one primary visual moment plus limited secondary context instead of concatenating unrelated prose.
- Continuity now exposes canonical character IDs in addition to legacy entity IDs.
- Prompt QA now validates the visual inference package, 9:16 image layout, required text box, provenance-separated character profiles, and reports aggregate failure counts.

The generated production prompts remain deterministic and source-grounded in story content while allowing explicitly labeled production inference for missing visual-generation details.

This upgrade is ready for local test validation. Do not mark the Asura DOD as passing until the full pytest suite and real 442-page DOD run both complete successfully.

# Project Checkpoint

## Latest real validation — 2026-09-10
The real Asura DOD run after the Docling precedence and prompt-QA fixes completed the full 442-page document.

### Verified
- pages: 442
- sections: 63
- stories: 63
- scenes: 191
- entities: 2078
- mentions: 6463
- aliases: 2109
- events: 191
- continuity entity states: 5140
- canonical characters: 18 confirmed + 7 singleton
- visual knowledge bible: 25 profiles, 3 facts
- canonical visual bible: 25 profiles, 3 facts
- contradictions: 0
- pages 11, 16, and 21 are now recognized as numbered structural headings:
  - 11 -> 1 The end
  - 16 -> 2 THE SEED
  - 21 -> 3 Captives

### DOD result
- QA passed: false
- QA failures: 117

This is a useful failure, not a reason to weaken the QA gate. The strengthened validator is now catching real prompt-package quality deficiencies.

### Prompt-quality finding
Manual inspection of the generated plan confirmed that canonical characters are present in the plan, but many have no source-supported visual facts (`visual_facts: []`, `unknown_visual_attributes: true`). That conservative behavior is correct; the system must not invent appearance.

However, the final image prompt is currently too shallow. It mostly concatenates narrative “visual moments” plus generic cinematic boilerplate and can combine unrelated moments. Character/profile context is not being compiled deeply enough into the final media prompts.

Example inspected scene included:
- Brahmins
- Lord Shiva
- Lord Vishnu
- Mithila

but the image prompt did not provide useful structured character/context information. The scene title also referenced `Ravana`, while the extracted character list did not include Ravana; this mismatch must be investigated.

### Performance observation
The real run shows RapidOCR using CPU. This contributes to long runtime for the 442-page PDF. Do not change OCR/backend solely for speed without validating source fidelity.

### Tomorrow — first tasks
1. Confirm full pytest result after latest fixture fix (expected 29 tests, but do not assume until run).
2. Categorize the 117 real QA failures by error type.
3. Inspect `media_prompt_compiler.py` / generation context path to determine why canonical visual/character context is not reaching final prompts deeply enough.
4. Improve prompt compilation without inventing unsupported visual facts.
5. Investigate scene-title/character mismatches such as `Captives Ravana`.
6. Review broader 63-section reconciliation; do not assume 63 is final desired chapter count.
7. Re-run targeted tests and a small set of real scenes before another full 442-page DOD run.

## Previous checkpoint

The repository's earlier checkpoint and project history remain preserved below this section.

## Current verified baseline
- End-to-end PDF → structure → scenes → generation plans → prompt export pipeline is operational.
- The Asura 442-page real-document run reaches prompt export, but the strengthened production QA currently reports 117 failures.
- Docling is the default low-level ingestion/layout/OCR/provenance backend.
- SQLite remains the canonical structured store.
- Character identity and visual grounding remain conservative: unsupported appearance must stay unknown.

## Current next steps
Use the “Latest real validation — 2026-09-10” section above as the authoritative restart point. Do not weaken QA to make the DOD pass. Focus next on prompt compilation quality, character/context propagation, scene-title/character reconciliation, and validation of the 63-section structure before another full run.
