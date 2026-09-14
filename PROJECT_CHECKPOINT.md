## Social Automation Project Checkpoint — 2026-09-14

### Current milestone: Production media-generation intelligence regression fix

All work remains isolated on `llm-local-qwen`; original `main` is untouched.

### Final fixes just applied
- Fixed the actual `camera_height` regression: `_camera_for()` uses the stable `height` field while `_prompt()` accepts both `camera_height` and `height`, so both current and legacy camera dictionaries are safe.
- Fixed generation-intent fallback ordering: when no trustworthy event candidates exist, source sentences are returned in source order, never keyword-reordered.
- Fixed character-presence semantics: only character-specific physical evidence can make a canonical character visible; a generic scene word such as `battle`, `destroyed`, or a memory/reference sentence cannot do so.
- Preserved strict source grounding and did not weaken the validator.
- Kept first-person narration separate from spoken dialogue.
- Kept referenced-only story/world characters available as context without silently rendering them.

### Why the previous run failed
The user's local run was on commit `7fca1c3` and reported **15 failed, 75 passed**. Twelve failures shared one root cause: `_prompt()` required `camera['camera_height']` while the generated camera dictionary exposed `height`. The other three were generation-intent regressions: fallback sentence order and character-presence classification. The failure log is preserved in the user's uploaded terminal output.

### Required verification — do not claim green until the user's machine confirms it
```powershell
cd M:\social-automation
git switch llm-local-qwen
git pull --ff-only origin llm-local-qwen
python -m compileall -q core tests
python -m pytest -q
python -m pytest tests\test_generation_intent.py tests\test_cinematic_generation.py tests\test_prompt_export.py tests\test_llm_runtime_hardening.py tests\test_scene_semantic_llm.py -q
python -m tools.check_ollama --model qwen3:30b
```

Only if the suite is green:
```powershell
$env:SOCIAL_AUTOMATION_LLM_MODE="shadow"
$env:SOCIAL_AUTOMATION_LLM_MODEL="qwen3:30b"
$env:SOCIAL_AUTOMATION_LLM_TIMEOUT="1800"
$env:SOCIAL_AUTOMATION_LLM_THINK="false"
$env:SOCIAL_AUTOMATION_LLM_CONTEXT="4096"

python -m core.generation_planner `
  "data\Asura\Asura - Tale Of The Vanquished_structure.db" `
  1 2 `
  --output scene2_final.json
```

Inspect the three exported media prompt files for Scene 2 before running all 191 scenes. Do not run `enhance` until the shadow output passes both automated QA and manual review.

### Production invariant
`SOURCE -> Generation Intent -> Media Planner -> Image/Short/Long` is the single flow. Source evidence controls what exists; world knowledge supplies context only; cinematic intelligence controls presentation only. No layer may fabricate a story event or promote a reference into a visible character without source-local physical evidence.
