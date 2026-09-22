# Asura Production Generation — Progress Ledger

Last updated: 2026-09-21

## Current repository state

- Repository: `MaheshKumar8045/social-automation`
- Branch: `llm-local-qwen`
- Current remote HEAD at checkpoint: `255d1b2` (`fix: normalize fallback canonical character row access`)
- Main branch has not been modified by this work.
- The local Windows working tree contains the current extractor fix; that fix is not yet represented by a new remote commit at this checkpoint.

## Source document

- PDF: `M:\\social-automation\\data\\Asura\\Asura - Tale Of The Vanquished.pdf`
- Pages: 442
- Sections: 63
- Scenes: 191
- Source DB: `M:\\social-automation\\data\\Asura\\Asura - Tale Of The Vanquished_structure.db`
- Document ID: 1

## Local verification status

The latest local verification before the real source pipeline was:

- Full pytest: **151 passed**
- Compileall: **passed**
- Focused character/identity/generation suite: **56 passed**

## Current production action

The corrected source pipeline has been started locally:

```powershell
.\\.venv\\Scripts\\python.exe -m core.pipeline "data\\Asura\\Asura - Tale Of The Vanquished.pdf"
```

Observed startup:

```
BOOK PROCESSING PIPELINE
Input PDF: data\\Asura\\Asura - Tale Of The Vanquished.pdf
```

The run was still in progress when this checkpoint was written.

## Why DOD is intentionally paused

Do **not** start the 191-scene DOD yet.

The prior DOD was expensive and exposed incorrect Scene 1 identity behavior. We found that the upstream entity extractor could suppress a character candidate when the same string was also detected as a location/environment candidate.

For Ravana, the previous DB contained:

```
King Ravana -> canonical character ID 30
Ravana -> incorrectly discovered as location
Ravana Tomorrow -> incorrectly discovered as character
```

The extractor fix removes the premature character suppression and lets the downstream candidate gate resolve the conflict.

The architecture remains:

```
source evidence
 -> entity extraction
 -> candidate gate
 -> identity resolution
 -> canonical character index
 -> generation context
 -> generation intent
 -> media prompts
 -> QA
 -> DOD
```

## Scene 1 acceptance gate

Before DOD, real-data Scene 1 must demonstrate:

- primary visual moment = `Tomorrow is my funeral.`
- narrative focus = `King Ravana`
- canonical Ravana ID = 30
- safe alias `Ravana` resolves to `King Ravana`
- `Ravana Tomorrow` is not treated as the canonical identity
- source-confirmed visible characters remain governed by source-local physical evidence
- image prompt contains `CANONICAL CHARACTER IDENTITY LOCK: King Ravana`
- no generation-planner/runtime exception

## Historical DOD result

The previous full DOD had 191 scenes but failed QA in 17 scenes with:

`image prompt does not contain any canonical character from the generation plan`

This is historical evidence only. Do not assume the same failures remain after the upstream fix.

## Next-session sequence

1. Let the currently running `core.pipeline` finish.
2. Inspect the regenerated DB/entity/identity results.
3. Run the targeted real-data Scene 1 generation-plan smoke test.
4. Confirm the Scene 1 acceptance gate above.
5. Run the full pytest suite again if the pipeline changed generated code paths or if the working tree changed.
6. Only then start the full 191-scene DOD.
7. After DOD, inspect `all_prompts.json` and QA before any refresh/apply step.

## Safety rules

- Never delete `data\\Asura\\`.
- Never run a second DOD while another expensive run is active.
- Never apply a package with `qa_passed=false`.
- Never manually edit the production DB to make Ravana pass.
- Never special-case Scene 1 in production code.
