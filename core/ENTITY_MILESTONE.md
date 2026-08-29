# Entity / Environment / Event Milestone

## Goal

Turn stored scenes into a reusable, source-grounded knowledge layer for later
character consistency, environment consistency, event-aware prompting, and RAG.

## Baseline

`EntityExtractor` discovers three entity types:

- `character` — likely proper names, title/name forms, and dialogue-attribution names
- `location` — capitalized phrases following common location cues
- `environment` — setting phrases such as a named river, village, cave, mountain,
  tunnel, sea, room, road, etc.

Every discovered entity retains evidence in `profile_text`, and every occurrence
is stored in `entity_mentions` with scene/story/page provenance.

`events` are intentionally conservative in this milestone: each scene is stored
as a source-grounded event candidate rather than receiving an invented semantic
summary.

## Storage

- `entities`
- `entity_mentions`
- `events`

The existing `documents -> sections -> stories -> scenes` hierarchy is preserved.

## Important boundary

This milestone does **not** claim semantic identity resolution. For example,
two differently formatted mentions that refer to the same person are not silently
merged unless the deterministic extractor produces the same canonical name.
Likewise, no appearance, personality, biography, or environmental facts are
invented.

A future semantic enrichment pass can resolve aliases, build canonical profiles,
and add confidence/evidence while keeping these source links.
