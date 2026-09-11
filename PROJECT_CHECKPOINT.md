## Character Identity QA — 2026-09-11

Generation Intelligence QA confirmed the emitted Asura package is structurally valid, but representative samples exposed split identity variants such as `Lord Shiva`, `Lord Shiva Pasupathi`, and `Lord Shiva Pasupathi Literally`.

### Current validation baseline
- Asura DOD: **passed** before the latest character-identity normalization change.
- PDF pages: **442**.
- Final reconciled sections: **63**.
- Stories: **63**.
- Scenes: **191**.
- Entities: **2078**.
- Mentions: **6463**.
- Aliases: **2109**.
- Events: **191**.
- Prompt QA: **passed**, **0 failures**.
- Previous canonical characters: **18 confirmed + 7 singleton**.
- Visual knowledge bible: **25 profiles, 3 facts, 17 objects, 192 object mentions, 191 scene contexts**.
- Canonical visual bible: **25 profiles, 3 facts, 25 source profiles, 0 contradictions**.
- Continuity: **5140 entity states, 5 state changes, 191 scene continuity records**.
- Prompt-quality audit: **191 scenes, 0 audit failures, 0 observations** after sampler correction.

### Fixes committed
- `core/character_identity_normalizer.py`
  - Added conservative qualified-name matching for titled identity prefixes with short epithet suffixes.
  - A one-word epithet may extend an exact titled identity; a two-word suffix is accepted only when the final word is an explicit qualification marker.
  - This is designed to merge forms such as `Lord Shiva` and `Lord Shiva Pasupathi Literally` without broad fuzzy identity collapsing.
- Added `tests/test_character_identity_qualifiers.py` covering positive qualified aliases and an unrelated `Lord Shiva` / `Lord Vishnu` non-match.

### Required validation
Regenerate the real Asura package after syncing `main`. The expected result is that qualified Shiva variants are consolidated into the same canonical identity group while unrelated titled characters remain distinct.

### Next local commands
```powershell
git pull
python -m pytest -q
python -m core.dod "data\Asura\Asura - Tale Of The Vanquished.pdf"
python -m core.prompt_quality_audit "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\all_prompts.json" --sample-count 8
```

After the run, inspect the sample output for:
1. `Lord Shiva` variants sharing one `identity_anchor`.
2. No `Who`, `Mithila`, or other obvious non-character becoming canonical characters.
3. Character-free scenes remaining character-free only when source evidence supports it.
4. World profile remaining contextual guidance rather than fabricated source facts.

### Known separate quality item
Docling still reports noisy OCR/recovered headings and 63 final sections despite numbered headings reaching 65. DOD is not blocked, but section reconciliation remains a separate quality item before section extraction is treated as final ground truth.

## Previous checkpoint

The World & Knowledge Intelligence v1 implementation used deterministic weighted source signal analysis, cached per document. Local pytest after classifier correction: **41 passed in 6.96s**.
