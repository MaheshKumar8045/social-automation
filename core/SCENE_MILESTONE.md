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

## Regression / verification status

The scene milestone is verified against the current repository baseline.

- Windows / Python 3.13 environment verified.
- Full automated regression suite: **25 passed, 0 failed**.
- SQLite connection lifecycle is now explicitly closed after use, including the
  scene milestone inspection path, preventing Windows temporary-directory file
  locking during test cleanup.
- The `DocumentStore` transaction/connection fix preserves the existing public
  APIs and keeps RAG/export behavior passing.

Verified repository commit:

```text
3a16978806937499ae0409067b15a36e08b50b4d
```

## Deliberate limitation

The current scene strategy is structural, not semantic. It does not claim that
every resulting scene is a true cinematic/narrative scene. A later semantic
segmenter can replace `paragraph_window` while keeping the same persistence and
provenance contract.

## Next

Proceed to the existing one-command PDF -> all-prompts DOD pipeline using a real
or benchmark PDF. Do not rebuild the scene/story persistence layer unless a new
regression is demonstrated.