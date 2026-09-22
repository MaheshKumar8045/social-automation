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
