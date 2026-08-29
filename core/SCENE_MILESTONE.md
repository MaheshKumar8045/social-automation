# Scene Milestone

## Completed

The core now provides a deterministic, source-grounded Section -> Story -> Scene
layer.

- `StorySegmenter` provides the baseline one-story-per-section contract.
- `SceneSegmenter` splits each story at paragraph boundaries into configurable
  scene-sized windows.
- Scene text is preserved verbatim from the stored story text.
- Scene records retain document, story, order, title, page range, method, and
  confidence.
- SQLite persists scenes with foreign keys and indexes.
- `DocumentStore.get_scenes()` provides read-only querying.
- JSON export includes scenes.
- `core.pipeline` writes `<name>_scenes.csv` and reports the scene count.

## Deliberate limitation

The current scene strategy is structural, not semantic. It does not claim that
every resulting scene is a true cinematic/narrative scene. A later semantic
segmenter can replace `paragraph_window` while keeping the same persistence and
provenance contract.

## Next

Use semantic analysis to refine story/scene boundaries and extract reusable
Character, Environment, Location, Event, and Relationship entities.
