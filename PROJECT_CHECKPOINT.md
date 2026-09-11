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
- Local pytest after the classifier correction: **41 passed in 6.96s**.
- Initial v1 classifier exposed a real bug where generic historical terms could outrank stronger mythology signals; fixed with weighted signal scoring and regression coverage.
- The first real Asura DOD after integrating world context reached the prompt-building stage but failed because `world_context.py` queried `sections.page_number`, while the canonical SQLite schema stores section start pages in `sections.page_start`.
- Fixed `core/world_context.py` to order section titles by `page_start` and aligned `tests/test_world_context.py` with the production section schema.
- GitHub commits: `fa05773185f740c4f03d6abb00a9a8f329ad1e31` (production fix), `69369bbdbe16da3eed080c2742b8f23d202663e9` (regression test schema fix).
- The failed DOD still confirmed the source pipeline itself completed successfully: 442 pages, 63 reconciled sections, 63 stories, 191 scenes, 2078 entities, 6463 mentions, 2109 aliases, and 191 events before prompt generation failed.

### Next validation
1. Sync local `main` with the latest GitHub commits.
2. Re-run the Asura DOD and confirm world-profile classification completes against the real SQLite schema.
3. Inspect world profile, several scene plans, visual inference, and final unified prompts.
4. Confirm source facts continue to override contextual inference and QA passes.
5. Later milestone: optional external knowledge enrichment (Wikidata/DBpedia/etc.) behind a provider interface; no LLM required for the baseline.

## Previous checkpoint

The repository's earlier checkpoint and project history remain preserved below this section.
