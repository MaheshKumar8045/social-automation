## Character Identity QA — 2026-09-11

Generation Intelligence QA confirmed the emitted Asura package is structurally valid, but representative samples exposed split identity variants such as `Lord Shiva`, `Lord Shiva Pasupathi`, and `Lord Shiva Pasupathi Literally`.

### Validation findings
- Baseline before identity tightening: **18 confirmed + 7 singleton = 25 canonical characters**.
- After the initial identity/gate tightening: **9 confirmed + 4 singleton = 13 canonical characters**.
- The 13-character DOD still passed structural QA, but the large drop was treated as a quality regression rather than accepted as correct.
- Prompt-quality audit remained **191 scenes, 0 failures, 0 observations**; this audit is structural/propagation-oriented and does not establish that the character inventory is complete.

### Root cause addressed
The candidate gate had a hard rejection whenever a character candidate shared its normalized name with a location/environment entity. That protection was too aggressive because legitimate source characters can share names with places or concepts.

### Current fix
- `core/character_candidate_gate.py`
  - Keep the cross-type collision protection for ambiguous names with no person evidence.
  - Preserve candidates that have direct person/speech/action evidence even when the same name also exists as a location/environment.
- `tests/test_character_candidate_gate.py`
  - Added regression coverage for the two cases: strong person evidence survives a location collision; weak location-only evidence is rejected.
- `core/character_identity_normalizer.py`
  - Retains conservative qualified-name matching for titled identity prefixes with short epithet suffixes.
- `tests/test_character_identity_qualifiers.py`
  - Covers `Lord Shiva` / qualified variants and keeps `Lord Shiva` distinct from `Lord Vishnu`.

### Required validation
Regenerate the real Asura package after syncing `main`. The corrected result should recover legitimate characters removed by the hard collision gate while still preventing place-only names from becoming canonical characters. Qualified Shiva variants should remain consolidated.

### Final local commands
```powershell
git pull
python -m pytest -q
python -m core.dod "data\Asura\Asura - Tale Of The Vanquished.pdf"
python -m core.prompt_quality_audit "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\all_prompts.json" --sample-count 8
```

After the run, inspect:
1. canonical-character count versus the prior 25-character baseline;
2. `Lord Shiva` variants sharing one `identity_anchor`;
3. no `Who`, `Mithila`, or similar place/common names becoming canonical characters;
4. character-free scenes remaining character-free only where source evidence supports it;
5. world profile remaining contextual guidance rather than fabricated source facts.

### Known separate quality item
Docling still reports noisy OCR/recovered headings and 63 final sections despite numbered headings reaching 65. DOD is not blocked, but section reconciliation remains a separate quality item before section extraction is treated as final ground truth.

## Previous checkpoint

The World & Knowledge Intelligence v1 implementation used deterministic weighted source signal analysis, cached per document. Local pytest after classifier correction: **41 passed in 6.96s**.
