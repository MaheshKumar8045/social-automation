## Prompt Quality Audit tooling — 2026-09-11

The real Asura end-to-end DOD is now green after the World & Knowledge Intelligence v1 SQLite schema fix.

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
- Canonical characters: **18 confirmed + 7 singleton**.
- Visual knowledge bible: **25 profiles, 3 facts, 17 objects, 192 object mentions, 191 scene contexts**.
- Canonical visual bible: **25 profiles, 3 facts, 25 source profiles, 0 contradictions**.
- Continuity: **5140 entity states, 5 state changes, 191 scene continuity records**.

### Prompt Quality QA milestone
Added `core/prompt_quality_audit.py` to inspect the emitted `all_prompts.json` package for intelligence propagation that structural QA alone cannot guarantee.

The audit checks:
- embedded scene QA status
- presence of document world profile
- narrative/culture/religious context observations
- world context appearing in final image prompts
- primary source visual moment presence
- character identity anchors
- separation of source facts and inferred facts
- visual inference structure
- representative scene previews

Added regression tests in `tests/test_prompt_quality_audit.py`.

### Next local validation
After syncing local `main`, run:
```powershell
python -m pytest -q
python -m core.prompt_quality_audit "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\all_prompts.json" --sample-count 8
```

Review the audit samples across early/middle/late scenes. Do not add another major enrichment feature until prompt quality and world-context propagation have been confirmed on the real Asura output.

### Known quality-review item
Docling still reports noisy OCR/recovered headings and 63 final sections despite numbered headings reaching 65. DOD is not blocked, but section reconciliation remains a separate quality item before section extraction is treated as final ground truth.

## Previous checkpoint

The World & Knowledge Intelligence v1 implementation used deterministic weighted source signal analysis, cached per document. Local pytest after classifier correction: **41 passed in 6.96s**.
