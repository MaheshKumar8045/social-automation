# Story Integration

This package integrates the baseline Section -> Story milestone into the current core.

- `StoryRecord` is the stable story contract.
- `StorySegmenter` currently creates one source-grounded story per detected section.
- `DocumentStore` creates/migrates the `stories` table and persists stories during `save_structure`.
- `DocumentStore.export_json()` includes `stories`.
- `core.pipeline` writes `<book>_stories.csv` and reports the story count.
- Existing content normalization, section detection, SQLite, CSV, and JSON behavior are preserved.

This baseline does not claim that a chapter is semantically one story. It provides a safe source-grounded unit for the next Scene milestone.
