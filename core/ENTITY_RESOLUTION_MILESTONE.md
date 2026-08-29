# Entity Resolution Milestone

## Goal
Convert discovered entity mentions into conservative, reusable canonical identities without inventing facts.

## Behavior
- Exact normalized spellings are consolidated.
- Titled character names can conservatively resolve to an unambiguous surname variant when the titled form is at least as confident.
- Locations and environments are not fuzzy-merged.
- Every resolved alias is retained in `entity_aliases`.
- Entity profiles aggregate source contexts only; they do not invent attributes.
- Mentions retain scene/story/page provenance.

## Outputs
- SQLite: `entities`, `entity_mentions`, `entity_aliases`
- JSON: `entity_aliases`
- CSV: `<book>_entity_aliases.csv`

This is intentionally deterministic. A later semantic/LLM resolver can propose additional merges, but those should remain evidence-backed and auditable.
