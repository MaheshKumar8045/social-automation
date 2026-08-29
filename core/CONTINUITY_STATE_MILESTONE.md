# Visual Continuity State Milestone

## Goal
Provide deterministic scene-to-scene state for downstream image/video generation without inventing source facts.

## Stored state
- Character presence per scene.
- Appearance, clothing, physical condition, and emotional state buckets.
- Scene-to-scene state changes with previous values, new values, change type, evidence, and confidence.
- Previous/next scene links.
- Persistent object mentions by scene.
- Environment state observed in each scene.
- Explicit continuity status: introduced, carried, or changed.

## Grounding rules
1. Source evidence remains attached to state.
2. Unknown attributes are not fabricated.
3. A later scene may add or change state without overwriting the canonical profile.
4. State changes are deterministic and auditable.

## CLI
```text
python -m core.continuity_state <database> <document_id>
```

## Next
Integrate continuity retrieval into `get_generation_context()` and add tests covering state carry-forward, updates, and unknown attributes.
