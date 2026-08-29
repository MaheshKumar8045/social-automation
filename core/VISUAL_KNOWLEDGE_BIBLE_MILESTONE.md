# Visual Knowledge Bible Milestone

## Purpose

Create an auditable, source-grounded visual continuity layer between document understanding and downstream image/video generation.

## v1 contract

The visual knowledge bible stores:

- character profiles derived from resolved character entities
- environment/location profiles derived from resolved location/environment entities
- visual facts with category, attribute, value, confidence, provenance, page range, scene and evidence
- recurring visual objects/props and the scenes in which they occur
- scene-level visual context linking characters, environments and props
- explicit continuity metadata stating that unsupported attributes must remain unknown

## Evidence policy

1. A fact is only `supported` when it has source evidence.
2. Every extracted fact records its extraction method and confidence.
3. Page/scene provenance is retained whenever available.
4. The system does not fill missing appearance attributes with generic assumptions.
5. Generation guidance must be derived from supported facts; it is not itself evidence.

## Current implementation

`core/visual_knowledge_bible.py` creates the v1 tables and deterministically extracts a conservative set of appearance, clothing, expression, mannerism, environment and prop evidence from the existing scene/entity layer.

It is intentionally independent of an LLM. This makes the layer inspectable and prevents generated guesses from becoming canonical facts.

## Next integration work

- wire the builder into `core.pipeline`
- add canonical retrieval/export methods
- add automated tests using an in-memory SQLite fixture
- expand source extraction beyond regex/lexicon baselines
- add temporal continuity/state changes without overwriting persistent identity facts
- expose a generation-context API that returns only evidence-backed visual constraints
