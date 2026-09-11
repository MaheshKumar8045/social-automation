## Asura DOD validation — 2026-09-11

The real Asura end-to-end DOD was rerun after fixing the World & Knowledge Intelligence v1 SQLite schema mismatch.

### Validation result
- DOD completed successfully.
- PDF pages: **442**.
- Final reconciled sections: **63**.
- Stories: **63**.
- Scenes: **191**.
- Entities: **2078**.
- Mentions: **6463**.
- Aliases: **2109**.
- Events: **191**.
- Pages stored: **442**.
- Prompt QA: **passed** with **0 failures**.
- Canonical characters: **18 confirmed + 7 singleton**.
- Visual knowledge bible: **25 profiles, 3 facts, 17 objects, 192 object mentions, 191 scene contexts**.
- Canonical visual bible: **25 profiles, 3 facts, 25 source profiles, 0 contradictions**.
- Continuity: **5140 entity states, 5 state changes, 191 scene continuity records**.

### Schema fix validated
- The DOD initially failed during world-profile construction because `world_context.py` queried `sections.page_number`, but the canonical SQLite schema stores section pagination in `sections.page_start` / `page_end`.
- The production query was corrected to order by `page_start`.
- The test fixture was also aligned to the production schema.
- After the fix, the full Asura DOD completed successfully with prompt QA passing.

### Important observation
The Docling diagnostics still show some noisy OCR/recovered chapter headings and a final reconciled count of 63 sections while numbered headings reach 65. This is not blocking DOD because the pipeline currently completes and prompt QA passes, but chapter/section reconciliation remains a quality-review item before treating section extraction as final ground truth.

### Next milestone — Generation Intelligence QA
Do not add another major feature yet. First inspect the generated `all_prompts.json` / representative scene plans and verify:
1. `world_profile` classification is correct for Asura (expected mythology/Hindu/Indic signals where source evidence supports them).
2. World context reaches character visual inference without becoming source truth.
3. `source_facts` and `inferred_facts` remain separate and source-grounded.
4. Canonical identity anchors remain stable across scenes.
5. Primary visual moment is scene-specific rather than mixing unrelated narrative moments.
6. Image prompts are genuinely mobile-first 9:16 and include deterministic dialogue/narrative overlay instructions.
7. Short-video clips, long-video shots, and audio packages stay consistent with the same scene truth.
8. Inspect several early/middle/late scenes plus scenes with sparse character evidence and recoverable/OCR-noisy headings.

### Later milestone
After Generation Intelligence QA passes, consider optional external knowledge enrichment behind a provider interface (for example Wikidata/DBpedia) with strict provenance. LLM enrichment remains optional and must not override source truth.

## Previous checkpoint

World & Knowledge Intelligence v1 was implemented with deterministic weighted source signal analysis, cached per document. Local pytest after classifier correction: **41 passed in 6.96s**.
