# Asura Production Generation — Progress Ledger

Last updated: 2026-09-20

## Current repository state

- Repository: `MaheshKumar8045/social-automation`
- Branch: `llm-local-qwen`
- Latest fix commit: `2ef4413c035fd40c4d3d2896bae71de191fce01d`
- Previous refresh/canonical-index fix: `ef85e295a5549d63bef3f3b24468b918b2b56afc`
- Previous upstream identity hardening commits are retained on this branch.
- Main branch has not been modified by this work.

## Source document

- PDF: `M:\social-automation\data\Asura\Asura - Tale Of The Vanquished.pdf`
- Pages: 442
- Sections: 63
- Scenes: 191
- Source DB: `M:\social-automation\data\Asura\Asura - Tale Of The Vanquished_structure.db`
- Document ID: 1
- Original package:
  `M:\social-automation\data\Asura\Asura - Tale Of The Vanquished_structure_prompts\all_prompts.json`
- Safety backup:
  `all_prompts.pre_visual_continuity.json`

## Expensive work already completed

The 191-scene DOD/LLM generation was already completed previously using local Qwen 3 30B shadow mode. It took approximately 9 hours.

Do NOT rerun the 191-scene DOD merely to address deterministic prompt/identity QA failures.

The expensive generation produced 191 scenes. The remaining work is deterministic refresh/validation unless a genuine source-semantic defect is discovered.

## Architecture decisions locked in

1. Source mention != scene participant != visible character.
2. Canonical character identity is distinct from physical visibility.
3. First-person narrator focus is allowed as controlled production inference, but it must never be treated as source-confirmed physical presence unless the source explicitly establishes physical presence.
4. Location/entity names such as Trikota and Lanka must not become characters merely because destruction/action verbs occur near them.
5. Source chronology controls visual-moment order. Salience must not move later material ahead of the actual opening moment.
6. LLM scene semantics are advisory. Deterministic source evidence is authoritative.
7. Image-model text rendering is disabled. Text is rendered later by the deterministic overlay renderer.
8. Refresh is zero-LLM and must fail closed. The source package is modified only when all 191 scenes pass QA.

## Root cause discovered for Scene 1

The source contains flattened first-person opening text equivalent to:

- `Ravana Tomorrow is my funeral.`
- later source material references Lanka and Trikota.

The canonical/entity layer had `King Ravana` while source mentions commonly used `Ravana`.

This caused the earlier pipeline to miss the narrator identity and allowed later city/location material to contaminate the opening visual interpretation.

The correct identity model is:

```
King Ravana
    -> safe source alias: Ravana

Ravana Tomorrow
Ravana Finally
Ravana Later
Only Ravana
Perhaps Ravana
    -> NOT safe identity aliases
```

## Fixes completed

### Candidate gate

`core/character_candidate_gate.py`

- Candidate evidence now reads `entity_mentions.mention_text` when available.
- Safe title variants are recognized.
- Royal/title qualifiers now include King, Emperor, Maharaja/Maharani, Prince/Princess, Queen.
- Physical presence uses the same conservative name variants.
- Legacy DB schemas without `mention_text` remain supported.
- Malformed OCR/entity strings are not promoted merely because they contain a valid character token.

### Identity normalization

`core/character_identity_normalizer.py`

- Royal/title prefixes are normalized consistently.
- `King Ravana` and `Ravana` can represent the same identity.
- Arbitrary suffix forms are still rejected.

### Mention identity resolution

`core/mention_identity_resolver.py`

- Title normalization now matches the canonical identity normalizer.

### Generation intent

`core/generation_intent.py`

- Uses safe character-name variants.
- First-person narrator resolution supports canonical/title-qualified identity versus bare source name.
- Physical presence remains sentence/evidence based.
- Source-order visual moments are preserved.
- Flattened narrator headings are handled without allowing later character references to steal narrator identity.

### Refresh

`core/refresh_media_prompts.py`

- Loads the document-wide canonical character index from the authoritative source DB.
- This allows a narrator omitted from scene-local character extraction to be resolved without inventing a new character.
- Refresh remains deterministic and zero-LLM.
- Existing package is never modified on QA failure.

### Media prompting

`core/media_prompt_compiler.py`

- Narrative-focus character is explicitly carried into the media prompt.
- The latest fix changes the narrator identity-lock label to exactly:
  `CANONICAL CHARACTER IDENTITY LOCK:`
- This aligns the prompt with the production QA contract.

### Regression coverage

Added tests for:

- titled canonical character -> safe bare source alias
- malformed `Ravana Tomorrow` rejection
- royal-title identity normalization
- titled canonical narrator resolution
- titled canonical physical presence
- location-versus-character separation
- location destruction not establishing character presence
- opening Asura narrator/visual moment behavior

## Latest refresh result before the final one-line QA fix

The deterministic refresh was run over all 191 scenes.

Result:

```json
{
  "scene_count": 191,
  "qa_passed": false,
  "qa_failures": 1,
  "qa_failure_counts": [
    ["image prompt is missing canonical character identity lock", 1]
  ],
  "model_calls": 0,
  "applied": false,
  "source_package_modified": false
}
```

This is a narrow production-contract mismatch, not a new 191-scene semantic-generation problem.

The existing prompt already emitted:

```
NARRATIVE FOCAL CHARACTER IDENTITY LOCK:
```

while `validate_plan()` requires the canonical production token:

```
CANONICAL CHARACTER IDENTITY LOCK:
```

Therefore the latest fix changes the emitted narrator lock label to the exact QA contract.

## Immediate next step tomorrow

Do NOT run DOD.

First run:

```powershell
cd M:\social-automation

git pull --ff-only origin llm-local-qwen

git rev-parse HEAD

.\.venv\Scripts\python.exe -m pytest -q \
    tests/test_character_candidate_gate.py \
    tests/test_character_identity_qualifiers.py \
    tests/test_generation_intent.py \
    tests/test_cinematic_generation.py \
    tests/test_prompt_export.py \
    tests/test_llm_runtime_hardening.py \
    tests/test_scene_semantic_llm.py
```

Then run the complete suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Then restore the pre-refresh backup before another refresh dry-run:

```powershell
$PROMPTS="M:\social-automation\data\Asura\Asura - Tale Of The Vanquished_structure_prompts"
$BACKUP="$PROMPTS\all_prompts.pre_visual_continuity.json"

if (!(Test-Path $BACKUP)) { throw "SAFE STOP: backup missing." }

Copy-Item $BACKUP "$PROMPTS\all_prompts.json" -Force

$CHECK="$PROMPTS\_visual_continuity_final_check"
Remove-Item $CHECK -Recurse -Force -ErrorAction SilentlyContinue

.\.venv\Scripts\python.exe -m core.refresh_media_prompts \
    "$PROMPTS\all_prompts.json" \
    --output-dir "$CHECK"
```

Expected next refresh result:

- scene_count = 191
- qa_passed = true
- qa_failures = 0
- model_calls = 0
- applied = false
- source_package_modified = false

Only after that passes should the Scene 1 production gate be run.

Only after the Scene 1 gate passes should the 191-scene package be applied with `--apply`.

## Important safety rule

Never skip the dry-run QA.

Never apply a package with `qa_passed=false`.

Never regenerate the full 191 scenes just because deterministic refresh QA found a prompt-contract defect.

## Known testing limitation at time of this update

The GitHub connector can inspect and modify the repository but cannot execute the user's Windows `.venv` directly.

The repository's existing GitHub Actions workflow is `.github/workflows/tests.yml` and is named `Python Tests`. A previous commit had a successful Actions run, but the latest commits have not been independently claimed as locally tested.

Therefore tomorrow's local Windows pytest run is the authoritative validation for the latest code state.

## Current stopping point

The current defect has been reduced to one deterministic QA mismatch:

```
missing canonical character identity lock
```

The code change to correct that exact contract is committed as:

```
2ef4413c035fd40c4d3d2896bae71de191fce01d
```

No source package has been modified by the failed refresh.

No image generation should be started yet.

Continue from the test -> refresh dry-run -> Scene 1 gate -> apply sequence above.
