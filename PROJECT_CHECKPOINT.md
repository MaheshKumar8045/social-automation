## Generation Intelligence QA — 2026-09-11

The real Asura end-to-end DOD is green after the World & Knowledge Intelligence v1 SQLite schema fix.

### Current validation baseline
- Asura DOD: **passed**.
- PDF pages: **442**.
- Final reconciled sections: **63**.
- Stories: **63**.
- Scenes: **191**.
- Entities: **2078**.
- Mentions: **6463**.
- Aliases: **2109**.
- Events: **191**.
- Prompt QA: **passed**, **0 failures**.
- Canonical characters: **18 confirmed + 7 singleton** in the pre-audit run.
- Visual knowledge bible: **25 profiles, 3 facts, 17 objects, 192 object mentions, 191 scene contexts**.
- Canonical visual bible: **25 profiles, 3 facts, 25 source profiles, 0 contradictions**.
- Continuity: **5140 entity states, 5 state changes, 191 scene continuity records**.

### Audit findings
The first real Asura prompt-quality audit confirmed that structural QA passed across all **191 scenes**, but exposed two quality-gate weaknesses:
1. The audit's `visual_inference_structure_unusual` observation incorrectly treated character-free scenes as unusual. This was a false positive in the audit logic.
2. Representative samples exposed obvious false-character risk, including `Who`, and a location-like entity such as `Mithila` appearing in the canonical-character layer. These cases were not blocked strongly enough before canonicalization.

### Fixes committed
- `core/character_candidate_gate.py`
  - Added `who` and related interrogative stopwords.
  - Added cross-entity-type protection: a character candidate whose normalized name is also classified as a location/environment is rejected.
- `core/character_canonicalizer.py`
  - Canonical singleton creation now requires an eligible `validated` or `probable` candidate; `review`/`non_character` members can no longer become canonical characters.
- `core/prompt_quality_audit.py`
  - Corrected visual-inference validation to require the package's explicit `enabled` flag rather than a non-empty character list.
  - Added obvious non-character-name detection.
  - Representative sampling now distributes samples across the package instead of inspecting only the first N scenes.
- Added `tests/test_generation_intelligence_audit.py` covering false-character rejection, canonicalization protection, and audit behavior.

### Important remaining validation
The source-generated Asura package itself must now be regenerated locally after syncing `main`. The next run should confirm whether the false character candidates disappear and whether canonical character counts change appropriately.

### Next local commands
```powershell
git pull
python -m pytest -q
python -m core.dod "data\Asura\Asura - Tale Of The Vanquished.pdf"
python -m core.prompt_quality_audit "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\all_prompts.json" --sample-count 8
```

Then inspect the audit samples, especially early/middle/late scenes and any scene that previously contained `Who`/location-like character candidates.

### Known separate quality item
Docling still reports noisy OCR/recovered headings and 63 final sections despite numbered headings reaching 65. DOD is not blocked, but section reconciliation remains a separate quality item before section extraction is treated as final ground truth.

## Previous checkpoint

The World & Knowledge Intelligence v1 implementation used deterministic weighted source signal analysis, cached per document. Local pytest after classifier correction: **41 passed in 6.96s**.
