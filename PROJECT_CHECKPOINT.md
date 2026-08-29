# Social Automation — Project Checkpoint

## Goal
Build a source-grounded book/PDF-to-visual-generation knowledge pipeline. The downstream generator must produce visually coherent scenes and frame-to-frame character/object/environment continuity, down to fine details. Unknown source information must remain unknown rather than being invented.

## Environment
- Local project: `M:\social-automation`
- Python: 3.13.15
- Windows PowerShell
- Virtual environment: `.venv`
- Git branch: `main`
- GitHub repo: `MaheshKumar8045/social-automation`
- Test PDF: `data\sample.pdf`
- Test SQLite DB: `data\sample_structure.db`
- Document ID: `1`

## Source processing baseline
For `data/sample.pdf`:
- PDF pages: 708
- Document type: mixed
- Final sections: 60
- Stories: 60
- Scenes: 332
- Events: 332
- Pages stored: 708
- Raw entities: 2,672
- Entity mentions: 6,088
- Aliases: 2,699

## Character pipeline — current verified run
### Conservative candidate gate
- validated: 30
- probable: 22
- review: 1,475
- non_character: 1,145

The gate was tightened repeatedly after observing false positives such as ordinary words, locations, institutions, and OCR fragments. Current design principles:
- bare single-word candidates require direct person evidence;
- generic geographic/institutional morphology is vetoed;
- OCR line-break fragments remain review/unresolved;
- candidate detection is conservative and reusable across books rather than sample-name hardcoded.

### Identity normalization
- groups: 39
- members: 52
- multi-member groups: 8

### Identity evidence
- identity_alias: 0
- ocr_fragment: 0
- unresolved: 8

### Mention identity resolution
Use `core/mention_identity_resolver.py` (the correct module name; earlier use of `core.mention_identity_resolution` was incorrect).
- confirmed_alias: 3
- likely_alias: 1
- ocr_fragment: 0
- unresolved: 4

### Canonical character layer
- confirmed: 3
- likely: 1
- singleton: 31
- excluded: 4
- usable canonical character records: 35

## Visual pipeline — current verified valid states
### Canonical Visual Bible
After rebuilding from the corrected character foundation:
- profiles: 35
- facts: 149
- source_profiles: 39
- contradictions: 97

### Visual fact reconciliation
- stable: 39
- stateful: 71
- contextual: 39
- conflicts: 30
- unsupported: 0

### Visual conflict classification
- low_evidence: 27
- scene_scoped: 3
- strong_conflict: 0

Interpretation: there are currently zero strong visual contradictions. Weak evidence and legitimate scene-scoped differences remain preserved rather than overwritten.

## Critical regression discovered
A later edit to `core/visual_knowledge_bible.py` added character-local visual evidence checks, but the first rebuild after that edit accidentally reverted character-profile selection to all raw entities. It produced:
- profiles: 2,672
- facts: 2,849
- objects: 31
- object_mentions: 303
- scene_context: 332

That run is INVALID and must not be treated as the canonical Visual Bible.

Root cause: the visual builder still iterates over `entities` directly. The character extractor was improved, but character profile selection was not properly connected to `canonical_characters` / `canonical_character_aliases`.

## Critical visual extraction lesson
The old extractor used broad regexes across the entire mention context. This caused false visual facts such as:
- `Colonel Everest -> build = small` from text about a “small tongue of platinum”;
- `Colonel Everest -> expression = serious` from “serious difficulty”;
- `David Livingstone -> build = large` from a “large scale map”.

The current local-evidence guard is intended to reject such unrelated matches. However, it must be retained while also limiting character profile construction to canonical characters.

## Required next engineering task
Fix `core/visual_knowledge_bible.py` so that:
1. character visual profiles are created from `canonical_characters` and `canonical_character_aliases`, not all raw entities;
2. the new character-local evidence extraction guard remains in place;
3. canonical character status/confidence are preserved;
4. unresolved identity groups are not connected;
5. environment/location profiles continue to be handled separately;
6. unknown visual attributes remain absent rather than inferred.

After this fix, rebuild and verify:
```powershell
python -m core.visual_knowledge_bible data\sample_structure.db 1
python -m core.canonical_visual_bible data\sample_structure.db 1
python -m core.visual_fact_reconciler data\sample_structure.db 1
python -m core.visual_conflict_classifier data\sample_structure.db 1
python -m core.scene_visual_state data\sample_structure.db 1 200 > scene_200.json
```

Regression expectation for scene 200:
- no bogus character attributes derived from unrelated phrases such as “large scale map”, “small tongue of platinum”, or “serious difficulty”;
- scene output remains source-grounded and keeps unknowns unknown.

## Useful temporary inspection files
Currently untracked local files include:
- `inspect_conflicts.py`
- `inspect_false_positives.py`
- `scene_200.json`
- CSV exports generated during processing

These are local test artifacts and should not be committed unless intentionally needed.

## Recent commits
- `31e7e8a` Require character-local evidence for visual facts
- `bc4d7cb` Strengthen generic false-positive suppression
- `483ca02` Require stronger evidence for un-titled ambiguous names
- `1d583a7` Add generic role and OCR fragment vetoes
- `6951e55` Reject generic geographic and institutional candidate names
- `7a04a0f` Require direct person evidence for bare-name candidates
- `d63f621` Require stronger evidence for single-word character candidates
- `f18d3e1` Fix scene visual state output and filter profile evidence
- `96793e6` Add scene-effective visual state retrieval

## Resume rule
Do not keep tuning the character gate unless a new regression demonstrates a specific false positive/false negative class. The current character foundation is considered good enough. Focus next on correctly wiring the canonical character layer into the visual knowledge builder, then regression-test scene visual state.
