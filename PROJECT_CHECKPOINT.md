## World & Knowledge Intelligence v1 — 2026-09-11

Implemented and integrated a lightweight, dependency-free document world-context layer.

### Architecture
- Added `core/world_context.py` for document-wide source signal analysis.
- The analyzer ranks narrative type, religious context, culture, region, and period using weighted source signals.
- Specific signals outweigh generic terms; e.g. explicit mythological entities outrank generic `king`/`kingdom` historical language.
- Each classification carries score, confidence, and triggering source terms.
- Low-confidence results remain provisional; missing dimensions remain unknown instead of being forced.
- `core/generation_context.py` builds the world profile dynamically per document and exposes it to generation.
- `core/generation_planner.py` carries the world profile into the generation plan and uses it for controlled character inference.
- `core/media_prompt_compiler.py` includes the detected world context in the unified media prompt while keeping it contextual rather than authoritative.
- `core/visual_generation_policy.py` uses `general_narrative` as the safe fallback instead of mythology.
- `config/visual_generation_policy.json` uses `general_narrative` as its default.
- Document world analysis is cached per database/document during a process to avoid rescanning every page for every scene.

### Evidence policy
1. Explicit source evidence is authoritative.
2. Strong source-derived context may guide production inference.
3. Deterministic world context may guide missing visual production details.
4. No exact eye color, hair color, height, exact age, or facial measurements are inferred without source evidence.
5. External knowledge bases and an LLM are intentionally not required for v1; the architecture can accept them later as optional enrichment providers.

### Validation status
- Local baseline before v1 integration: 36 tests passed.
- Initial v1 classifier exposed a real bug where generic historical terms could outrank stronger mythology signals.
- Fixed with weighted signal scoring and added regression coverage for mixed mythology/historical wording.
- Current GitHub `main` contains the classifier fix and updated tests; local validation is required after sync.
- The prior synchronized Asura DOD run completed all 442 pages, 191 scenes, and prompt QA with 0 failures, but that run preceded the final world-classification correction.

### Next local validation
- Sync local `main` with the latest GitHub commits.
- Run the full pytest suite; expected count is now 41 tests.
- Re-run the Asura DOD after the classifier fix and world-context integration.
- Inspect several generated scene plans to verify the world profile is dynamic and reaches visual inference/prompts.
- Later milestone: optional external knowledge enrichment (Wikidata/DBpedia/etc.) behind a provider interface; no LLM required for the baseline.

## Previous checkpoint

The repository's earlier checkpoint and project history remain preserved below this section.
