# Story Segmentation Milestone

Implemented in this package:

- `StoryRecord` source-grounded model.
- `StorySegmenter` deterministic baseline.
- Each detected section becomes one story unit.
- Story units retain section, page range, full canonical source text,
  segmentation method, order, and confidence.
- SQLite `stories` table with section foreign key and indexes.
- `DocumentStore.get_stories()` and JSON export support.
- Pipeline emits `<name>_stories.csv`.

## Important boundary

This milestone does **not** claim semantic story splitting. A chapter/section
may contain multiple narrative arcs. The deterministic baseline intentionally
does not invent those boundaries. `StorySegmenter` is the extension point for
a later semantic/AI strategy.

Next: semantic Story refinement, then Story -> Scene.
