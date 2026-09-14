## Social Automation Project Checkpoint — 2026-09-14

### Current milestone: Source-grounded cinematic participant handling

All work remains isolated on `llm-local-qwen`; original `main` is untouched.

### Final hardening applied
- Fixed generation-intent fallback ordering: when no trustworthy event candidates exist, source sentences are returned in source order, never keyword-reordered.
- Fixed character-presence semantics: only character-specific physical evidence can make a canonical character visible; generic scene words, memories, references, or unrelated speech/action cannot do so.
- Preserved strict source grounding and did not weaken the semantic validator.
- Kept first-person narration separate from spoken dialogue.
- Kept referenced-only story/world characters available as context without silently rendering them.
- Added a separate `source_participants` channel for anonymous groups/participants explicitly named by the scene (for example `the enemy` or `the monkey-men`). These are not canonical identities and cannot acquire unsupported identity attributes.
- Propagated source-established anonymous participants into image, short-video, and long-video prompts with an explicit instruction to depict only the action/visual level supported by the scene text.
- This solves the key Scene 2 quality gap without weakening canonical-character identity rules.

### Production invariant
`SOURCE -> Generation Intent -> Media Planner -> Image/Short/Long` is the single flow. Source evidence controls what exists; world knowledge supplies context only; cinematic intelligence controls presentation only. Canonical character visibility requires source-local physical evidence. Anonymous source-established participants may be depicted only when explicitly named by the scene and only at the level supported by that source evidence.

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

Only if the suite is green, regenerate Scene 2 in shadow mode:
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

Inspect the three exported media prompt files for Scene 2. Confirm that source-established groups such as the enemy/monkey-men can be depicted while canonical names remain governed by strict source-local presence rules. Do not run the 191-scene Qwen job or `enhance` until this scene passes automated QA and manual review.
