# Cinematic Adaptation Engine

This branch adds a planning layer above the stable Google AI Mode image pipeline.

## Design checklist

1. Scene-to-shot expansion instead of one image per extracted scene.
2. Source-grounded visual beats and shot roles.
3. Character identity locks and continuity carry-forward.
4. Episode/sequence grouping.
5. Narration and dialogue manifests.
6. Deterministic subtitle timelines.
7. Per-shot image TXT files compatible with the existing image pipeline.
8. Per-shot video-generation manifests.
9. Source-grounding QA before a package is considered ready.
10. The existing image-generation branch remains unchanged as the rollback path.

## Input

Prefer the exported canonical package:

data/<book>_structure_prompts/all_prompts.json

It contains source scene text, canonical characters, continuity, generation intent, long-video shots, and audio direction.

TXT scene prompts are supported as a fallback, but the canonical JSON package contains substantially more source structure.

## Build

python -m core.cinematic_adaptation ^
  "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\all_prompts.json" ^
  --output-dir "data\Asura\Asura - Tale Of The Vanquished_structure_cinematic" ^
  --min-shots 3 ^
  --max-shots 8 ^
  --scenes-per-episode 10

The command exits with code 2 if source-grounding QA fails.

## Output

* cinematic_adaptation.json: complete episode and shot plan.
* qa_report.json: source-grounding QA.
* episode_*.json: episode-level shot/audio/continuity packages.
* episode_*_narration.txt: ordered voice-over script.
* episode_*.srt: deterministic subtitle timeline.
* shots/image/: scene_*.txt files directly consumable by core.image_pipeline.
* shots/video/: per-shot video-generation manifests.
* audio/: per-shot voice/music/sound-design manifests.
* subtitles/: per-shot overlay timing manifests.

The adaptation layer does not generate images or video itself. It produces a richer, source-grounded production plan for those generation stages.

## Assemble generated images into episode videos

After the existing image pipeline has generated the shot images:

python -m core.cinematic_assembly ^
  "data\Asura\Asura - Tale Of The Vanquished_structure_cinematic\cinematic_adaptation.json" ^
  --image-root "data\Asura\Asura - Tale Of The Vanquished_structure_cinematic\generated_images" ^
  --output-dir "data\Asura\Asura - Tale Of The Vanquished_structure_cinematic\assembly"

The command creates per-episode concat manifests and ffmpeg commands. Add --render after ffmpeg is installed and all shot images exist to render MP4 episodes locally.
