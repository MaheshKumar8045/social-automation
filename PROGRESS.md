# Project Progress Checkpoint

## Latest checkpoint — 2026-09-23

### Current focus

The active production work is now the **cinematic image-generation pipeline** for:

- Source PDF: `M:\\social-automation\\data\\Asura\\Asura - Tale Of The Vanquished.pdf`
- Source: 442 pages
- Planned scenes: 191
- Output goal: consistent 9:16 portrait images, zero model-generated text, deterministic source-dialogue overlays, canonical character continuity, resumable generation, and clean QA.

### Image-generation pipeline status

The following production fixes are now implemented on `image-generation-pipeline`:

1. **Google AI Mode / Chrome CDP**
   - Supports attaching to a manually signed-in dedicated Chrome profile through `--chrome-cdp-url`.
   - Avoids the earlier login/profile automation problem.

2. **Google AI Mode daily-limit handling**
   - Dedicated `GoogleAIModeDailyLimitError`.
   - Interrupted scene is persisted as `RETRY`, not permanently `BLOCKED`.
   - CLI exits cleanly when the Google daily limit is reached.
   - Rerunning after switching account/profile can therefore resume the interrupted scene.

3. **Sequential scene artifact naming**
   - `scene_order` is not unique in the real data, so it must not be used as the directory sequence.
   - New artifact directories use loaded-job sequence plus actual scene ID:
     - `scene_001_00001`
     - `scene_002_00004`
     - `scene_003_00006`
   - Final artifacts use:
     - `scene_001_00001_final.png`
     - `scene_002_00004_final.png`
   - Legacy directories/final names are migrated on pipeline startup and SQLite paths are repointed.

4. **Exact portrait output**
   - Generated artwork is normalized to exactly **720x1280 / 9:16** before validation and overlay rendering.
   - Current normalization uses a centered crop followed by Lanczos resize; revisit with subject-aware cropping if future scenes show important side-subject loss.

5. **Zero generated-text protection**
   - Image prompt explicitly requires zero readable text/typography.
   - Quoted source dialogue is kept for deterministic overlays but removed from visual moments sent to the image model.
   - Clean generated artwork is OCR-checked before overlay rendering.
   - Meaningful unexpected OCR text causes image-generation retry.
   - PaddleOCR initialization is cached.

6. **Deterministic overlay renderer**
   - Source dialogue is rendered after image generation.
   - Transparent text-only overlay; no opaque dialogue panel.
   - Warm parchment text with dark outline and restrained shadow.

### Latest overlay issue and fix — 2026-09-23

The latest real image exposed two overlay problems:

- The lower dialogue block became too small because the renderer's maximum height was too restrictive.
- The lower dialogue was placed over a character's legs because mean visual-detail scoring could treat a mostly quiet foreground region as safe even when a localized subject occupied part of it.

Implemented fix:

- Increased dialogue overlay working area from roughly **68% width / 15% height** to **80% width / 30% height**.
- Increased the production overlay font baseline so long dialogue does not collapse into tiny typography.
- Added localized **foreground/subject occupancy scoring** using tiled edge/contrast analysis.
- Placement now penalizes concentrated detail from bodies, legs, hands, weapons, foreground silhouettes, and other localized subjects instead of relying only on average region detail.
- Existing overlay-overlap and center-action penalties remain.
- Updated the media-generation contract to explicitly avoid faces, heads, bodies, legs, hands, foreground silhouettes, important objects, and primary action.
- Added a regression test with a busy foreground region to ensure long dialogue moves away from that area.

### Latest relevant commits

- `3bc4522` — protect foreground subjects during dialogue overlay placement
- `60d5f32` — enlarge dialogue overlay safe area
- `d3a97a9` — strengthen overlay subject-avoidance contract
- `3355c2d` — clean overlay regression-test fixture imports

### Last real local generation evidence

The recent local pilot used:

```powershell
.venv\\Scripts\\python.exe -m core.image_pipeline `
  "data\\Asura\\Asura - Tale Of The Vanquished_structure_prompts\\all_prompts.json" `
  --output-dir "data\\Asura\\Asura - Tale Of The Vanquished_structure_prompts\\generated_images_overlay_v2" `
  --limit 3 `
  --max-attempts 3 `
  --generation-timeout 300 `
  --no-vision `
  --chrome-cdp-url "http://127.0.0.1:9222" `
  --verbose
```

Observed summary after switching account/profile:

```
blocked: 1
completed: 3
pending: 187
```

The logs initially appeared to repeat "scene 1", but the actual output showed multiple jobs with `scene_order=1`; this directly motivated the sequential directory-name fix. The interrupted daily-limit scene was therefore retriable rather than lost.

### What still needs local verification

Do **not** assume the new overlay fix is production-proven until the local pipeline generates a fresh sample.

Next run should use a fresh output directory so completed SQLite records do not hide the new behavior:

```powershell
cd M:\\social-automation
git pull origin image-generation-pipeline
.venv\\Scripts\\python.exe -m core.image_pipeline `
  "data\\Asura\\Asura - Tale Of The Vanquished_structure_prompts\\all_prompts.json" `
  --output-dir "data\\Asura\\Asura - Tale Of The Vanquished_structure_prompts\\generated_images_overlay_v3" `
  --limit 10 `
  --max-attempts 3 `
  --generation-timeout 300 `
  --no-vision `
  --chrome-cdp-url "http://127.0.0.1:9222" `
  --verbose
```

Verify for the first 10 generated scenes:

- final dimensions are exactly 720x1280;
- no model-generated text survives clean validation;
- deterministic dialogue is readable at a consistent size;
- dialogue does not cover faces/bodies/legs/hands/important foreground subjects;
- directories are sequential by loaded job order;
- final filenames follow `scene_00x_0000x_final.png`;
- daily-limit interruption still persists as `RETRY` and resumes after account/profile change.

### CI status at checkpoint

The overlay test suite reached **160 passed**; the only two failures were the pre-existing `tests/test_generation_context.py` ordering bug where the query used `em.id` although the fixture's `entity_mentions` table has no `id` column. That is now fixed by ordering on the existing `em.entity_id` column. A fresh GitHub Actions run is expected from that fix; verify it before the next production pilot.

### Tomorrow's resume point

1. Read this latest checkpoint first.
2. Pull the current `image-generation-pipeline` branch.
3. Check the latest CI result and confirm the generation-context fix leaves the suite green.
4. Run the fresh `generated_images_overlay_v3` 10-scene pilot.
5. Inspect several final PNGs, especially long-dialogue scenes.
6. If overlay placement/readability passes, continue production image generation.
7. If the new subject-safe placement still misses a foreground subject, improve the renderer from actual failing evidence rather than adding a fixed bottom exclusion rule.
8. Preserve existing v2 artifacts for comparison; do not delete `data\\Asura\\`.

---

# Project Progress Checkpoint

## Checkpoint date

2026-09-21

## Current objective

Complete the production end-to-end pipeline for:

- Source PDF: `M:\\social-automation\\data\\Asura\\Asura - Tale Of The Vanquished.pdf`
- Source size: 442 pages
- Current scene count: 191
- Goal: a correct 191-scene cinematic generation/prompt package with canonical identity, narrative focus, visual continuity, and QA passing.

## Current stopping point

The local Windows working tree has the extractor fix applied and the local regression suite is green.

The user has now started the real source pipeline:

```powershell
.\\.venv\\Scripts\\python.exe -m core.pipeline "data\\Asura\\Asura - Tale Of The Vanquished.pdf"
```

The pipeline has reached:

```
============================================================
BOOK PROCESSING PIPELINE
============================================================
Input PDF: data\\Asura\\Asura - Tale Of The Vanquished.pdf
```

At this checkpoint, completion output from that run has not yet been reported. Let that run finish before starting another pipeline/DOD run.

## Important: do NOT run DOD yet

The earlier 191-scene DOD exposed production-only problems and also showed incorrect Scene 1 identity data.

The current objective is to prove the corrected upstream entity/identity path first:

```
PDF
 -> entity extraction
 -> candidate gate
 -> identity resolution
 -> canonicalization
 -> generation context
 -> Scene 1 generation plan
 -> prompt QA
 -> only then full DOD
```

Running DOD before this gate passes would regenerate expensive artifacts from potentially incorrect upstream data.

## Root cause currently being fixed

The production DB previously contained:

- canonical character: `King Ravana`, ID 30
- valid source alias: `Ravana`
- a character entity: `Ravana Tomorrow`
- a separate `Ravana` entity incorrectly classified as `location`

The entity extractor was prematurely suppressing character candidates whenever the same text was also discovered by the location/environment heuristics.

The local fix removes that premature suppression so conflicting candidate types can coexist and the downstream character candidate gate can make the authoritative decision.

This is intentionally an upstream fix. Do NOT solve the problem with `Tomorrow` stopwords, substring matching, manual DB edits, or Scene 1 special cases.

## Local verification already completed

Before starting the real PDF pipeline:

- Full pytest suite: **151 passed**
- Compile check: **passed**
- Focused character/identity/generation suite: **56 passed**

The local working tree fix is not yet represented by a new remote code commit at this checkpoint.

## Previous production evidence

The previous full DOD produced:

- 442 pages
- 63 sections
- 191 scenes
- 17 prompt QA failures

The failures were:

`image prompt does not contain any canonical character from the generation plan`

Scene 1 also previously had:

- narrative focus missing
- visible canonical characters: 0
- canonical Ravana not resolved into scene-local generation context
- no canonical identity lock

A direct real-data smoke test also exposed a fallback row-shape bug in `core/generation_context.py`; that bug is fixed on the current branch.

## Required next validation after pipeline finishes

First verify the regenerated real DB, especially:

1. `Ravana` is present as a `character` entity rather than only a location.
2. The candidate gate no longer rejects that Ravana entity solely because of upstream type.
3. The identity layer connects the safe alias `Ravana` to canonical `King Ravana` (ID 30).
4. Scene 1 generation context resolves `King Ravana`.
5. Scene 1 primary visual moment remains `Tomorrow is my funeral.`.
6. Scene 1 has no source-confirmed physical visible character unless the source actually establishes one.
7. Scene 1 image prompt contains:
   - `NARRATIVE FOCAL CHARACTER (CONTROLLED PRODUCTION INFERENCE): King Ravana`
   - `CANONICAL CHARACTER IDENTITY LOCK: King Ravana`

Only after these checks pass should the 191-scene DOD be started.

## Operational rules

- Never delete `data\\Asura\\`.
- Do not start DOD while the source pipeline is still running.
- Do not rerun a multi-hour DOD to diagnose an upstream entity/identity defect.
- Do not apply a refresh/package when QA is false.
- Preserve previous DOD artifacts for forensic comparison.
- Prefer targeted real-data validation before expensive generation.

## Resume instruction

Tomorrow, read this file first.

Then continue from the currently running `core.pipeline` result. Do not restart the investigation from the historical DOD failure. The next gate is real-data Ravana/entity/identity validation, followed by a Scene 1 generation-plan smoke test, and only then full DOD.
