# Project Progress Checkpoint

## Current objective

Complete the production end-to-end pipeline for:

- Source PDF: `M:\\social-automation\\data\\Asura\\Asura - Tale Of The Vanquished.pdf`
- Expected source size: 442 pages
- Existing scene count: 191
- Goal: produce a correct 191-scene cinematic generation/prompt package with canonical identity, narrative focus, visual continuity, and QA passing.

## Active DOD run

- Run ID: `20260921_131806`
- Started: 2026-09-21 13:18:06
- Mode: `shadow`
- Model: `qwen3:30b`
- LLM timeout: 1800 seconds
- Qwen thinking: disabled
- Full DOD rebuild is currently in progress.
- Do NOT start another DOD run unless this run fails and its failure has been diagnosed.

Run checkpoint directory:

`M:\\social-automation\\data\\Asura\\DOD_RUN_20260921_131806\\`

Expected checkpoint files:

- `previous_structure.db`
- `previous_all_prompts.json`
- `dod_full.log`

## Current phase at last update

The full DOD run had reached the Docling PDF scan phase.

Observed messages included:

`RapidOCR returned empty result!`

These were observed during Docling processing and had not been established as a pipeline failure.

Next expected stages:

1. PDF / Docling scan
2. Document structure
3. SQLite structure DB
4. Scene extraction
5. Character/entity extraction
6. Canonical identity
7. Visual facts/profiles
8. Event extraction
9. Qwen semantic extraction
10. Generation intent
11. Cinematic/media compilation
12. Visual continuity
13. Prompt export
14. QA
15. Scene 1 validation
16. Full artifact validation

## Critical investigation history

The previous full DOD run took approximately 9 hours and produced:

- 442 pages
- 63 sections
- 191 scenes

However Scene 1 was incorrect.

Expected Scene 1:

- Primary visual moment: `Tomorrow is my funeral.`
- Narrative focus: `King Ravana`
- Visible characters: none
- Canonical Ravana ID: 30

Previous incorrect result:

- Primary visual moment contained the entire opening paragraph beginning with `1 The end Ravana Tomorrow is my funeral...`
- Narrative focus was blank
- Visible characters: 0
- Ravana was absent from scene-local characters

## Real-data diagnosis completed before current rebuild

The authoritative structure DB was confirmed:

`M:\\social-automation\\data\\Asura\\Asura - Tale Of The Vanquished_structure.db`

It contains 76 canonical characters.

Ravana record:

- canonical_character_id: 30
- canonical_name: King Ravana
- status: confirmed
- confidence: 1.0
- aliases:
  - King Ravana
  - King Ravana Prabhu
  - Maharaja Ravana

The actual Scene 1 source was inspected and begins with:

`1 The end Ravana Tomorrow is my funeral...`

Both production narrator resolvers were tested directly against the real source and real canonical database:

- Standard resolver -> `King Ravana`
- Refresh resolver -> `King Ravana`

Therefore the investigation ruled out a simple missing-canonical-record or narrator-resolution problem.

The deterministic refresh nevertheless produced the old Scene 1 semantics, even after the resolver fix. Because the user did not want to spend more time debugging a generated artifact, the decision was made to perform a clean full DOD rebuild from the source PDF.

## Code fixes already on branch

Branch: `llm-local-qwen`

Relevant commits:

- `ad3b4f2` fix: recover narrator directly from canonical aliases during refresh
- `bcefbd3` test: lock canonical focus injection before media compilation
- `a14b054` fix: inject resolved canonical focus before media compilation
- `2087ad2` fix: make canonical document IDs immutable during refresh merge
- `df545c7` test: expose canonical database selection in refresh regression
- `453f988` fix: fail fast when canonical document index cannot be loaded
- `6aae505d` test: cover local structure DB precedence and narrator collision
- `caac3ace` fix: resolve authoritative structure DB before embedded paths
- `5fc8d5f` fix: preserve authoritative identity on scene ID collision

Focused regression suite was green with 73 passing tests before the current full rebuild.

## Important operational rules

- Never delete `data\\Asura\\`.
- Do not rerun the expensive DOD while the current run is still active.
- Do not assume a generated artifact is correct merely because deterministic refresh QA passes.
- After the current DOD completes, validate the actual generated `all_prompts.json`, especially Scene 1, before any refresh or further modifications.
- Preserve `DOD_RUN_20260921_131806` and its log for forensic comparison.
- If the current run fails, diagnose the exact phase/scene/source transformation before starting another expensive run.

## Required final validation

After DOD completes, inspect the newly generated package and verify at minimum:

```
Scenes: 191
QA: True

Scene 1:
Primary: Tomorrow is my funeral.
Focus: King Ravana
Visible count: 0
Ravana ID: 30
```

Then validate the complete QA result and inspect any remaining failures before declaring the package complete.

## Resume instruction

When returning to this project, read this file first. The current checkpoint is the active full DOD run `20260921_131806`. Continue from the recorded phase/result rather than restarting investigation from scratch.


## 2026-09-21 production DOD failure and review checkpoint

The full DOD rebuild reached the prompt-generation stage after successfully rebuilding the source database:

- 442 pages
- 63 sections
- 63 stories
- 191 scenes
- 2078 entities
- 6463 mentions
- 2109 aliases
- 191 events

It then failed on Scene 1 with:

`NameError: name 'scene' is not defined`

in `core/generation_context.py::_characters()`.

A first attempted fix accidentally inserted a literal escaped newline, producing a second failure:

`NameError: name 'presence_contexts' is not defined`.

The correct fix is now committed as `ca55c61`:

- `presence_contexts = [scene_text] if scene_text else []`

The focused regression suite had passed after the first fix, but the real DOD exposed a production-only scope path that the tests did not cover.

### Additional critical review finding

During a deeper end-to-end code review, a second production bug was found before another expensive DOD run:

`core/generation_planner.py::_prompt_bundle()` called `compile_media_prompts()`, which correctly received the deterministic `context["narrative_focus_character"]`, but then called `enhance_generation_package()` without passing that focus.

`enhance_generation_package()` rebuilds `generation_intent`, so the resolved first-person narrator focus could be lost from the final DOD generation intent even though the earlier media compiler had it.

This directly explains the historical symptom where Scene 1 had a correct source moment but blank narrative focus in the final package.

Fix committed as `00c6a6b`:

- preserve `narrative_focus_character` through `_prompt_bundle()`
- pass it explicitly into `enhance_generation_package()`

A new regression test was added:

- `tests/test_generation_planner.py`
- verifies the resolved narrative focus survives the planner-to-cinematic-enhancement boundary.

Additional QA hardening committed as `01be86f`:

- `validate_plan()` now requires `media.generation_intent`
- if a narrative focal character exists, the final image prompt must contain that canonical focal character name.

### Current sign-off status

**NOT YET SIGNED OFF.**

The source database/pipeline extraction is proven to complete, but the current branch has just received the planner focus-propagation fix and QA hardening. Before another full DOD run, run:

1. Python compile check for the project.
2. Full pytest suite, not only the five focused suites.
3. Targeted generation-planner regression.
4. A deterministic generation-plan smoke test using the rebuilt Asura structure DB if available.
5. Only then run the full DOD.

Do not spend another multi-hour DOD run until these checks pass.

### Required DOD acceptance criteria

After the next full run:

- DOD exits successfully.
- 191 scenes exported.
- QA passed with zero failures.
- Scene 1 primary moment = `Tomorrow is my funeral.`
- Scene 1 narrative focus = `King Ravana`.
- Scene 1 visible canonical characters = none.
- Scene 1 contains canonical Ravana ID 30.
- Scene 1 image prompt contains the narrative focal-character contract and canonical identity lock where applicable.
- No scene-generation exception occurs.


### CI review finding after QA hardening

GitHub Actions compile check passed on commit `42ccbad`, but the full pytest suite initially failed 4 tests because the existing test fixture represented a pre-schema-6 media package without `media.generation_intent`.

This was a **test fixture compatibility issue introduced by the new QA assertion**, not a production runtime failure. The fixture has now been updated in commit `963f2e3` to include:

`media.generation_intent.narrative_focus_character = None`.

The next CI run must be green before sign-off.


### Pre-DOD signoff gate

Before another full DOD run, use the already rebuilt Asura structure DB for a one-scene real-data planner smoke test. This avoids spending hours before verifying the exact production path that previously failed.

Required smoke-test assertions for Scene 1:

- planner completes without exception
- primary visual moment = `Tomorrow is my funeral.`
- narrative focus = `King Ravana`
- visible canonical characters = none
- canonical Ravana ID = 30
- image prompt contains `NARRATIVE FOCAL CHARACTER (CONTROLLED PRODUCTION INFERENCE): King Ravana`
- image prompt contains `CANONICAL CHARACTER IDENTITY LOCK: King Ravana`

The full DOD should not be restarted until this smoke test and the full pytest suite are green.

## Latest production smoke-test finding (2026-09-21)

After the full DOD rebuild reached prompt generation, a direct real-database Scene 1 smoke test exposed a second runtime bug that the 150-test suite had not covered:

- `core/generation_context.py::_characters()` merged fallback canonical-character SQLite rows selected as `id` into rows expected to contain `canonical_character_id`.
- Real execution therefore failed with `IndexError: No item with that key` when fallback character recovery was exercised.
- Fixed by aliasing the fallback query column to `canonical_character_id`.
- Fix commit: `f4ab8c6` (`fix: normalize fallback canonical character row ids`).
- Added regression test: `99cd6b8` (`test: cover fallback canonical character row shape`).

The previous 150 passing tests were not sufficient evidence for production sign-off because they did not exercise this real fallback-row path. **Do not rerun the 9-hour DOD until the latest code passes compile, the full test suite, and a direct real Asura Scene 1 generation-plan smoke test.**
