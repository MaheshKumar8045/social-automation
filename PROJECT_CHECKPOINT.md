## Social Automation Project Checkpoint — 2026-09-14

### Current milestone: Production media-generation intelligence implemented

All work remains isolated on `llm-local-qwen`; original `main` is untouched.

### Implemented in this milestone
- Added `core/generation_intent.py` as the shared source-of-truth layer for media generation.
- Added complete source-grounded visual-moment selection with sentence-complete evidence.
- Added explicit visible/referenced character separation.
- Added first-person narration vs spoken-dialogue classification.
- Added controlled cinematic arc planning.
- Reworked `core/cinematic_generation.py` so Image, Short Video, and Long Video consume the same generation intent.
- Image generation now uses one dominant source visual moment, explicit composition intent, safe text space, and environment-first behavior when no character is source-confirmed.
- Short Video now has a three-beat progression with distinct camera intents, transitions, source focus, and synchronized voice/audio metadata.
- Long Video now uses a dynamic 4–8 shot plan with shot-purpose taxonomy, distinct camera grammar, source-moment allocation, spatial-continuity instructions, and per-shot duration/dialogue metadata.
- Audio now distinguishes spoken dialogue, first-person narration/voice-over, and no-source-dialogue cases; `dialogue_source` matches rendered voice text.
- Added shared `generation_intent` to the unified media package.
- Added regression coverage for source completeness, narration classification, character presence, camera diversity, dynamic shot planning, audio alignment, and shared intent propagation.
- Added GitHub Actions Python compile/test workflow for future push/PR validation.

### Validator decision remains unchanged
The strict source-grounding validator was not weakened. Story/world knowledge remains separate from scene-local evidence, and referenced-only characters cannot silently become visible characters.

### Current branch head
- `llm-local-qwen`: `80dc170f0e33dee0e43cb8393264cb3b27578720` plus the production-intelligence commits recorded after it.
- Stable `main` was not modified.

### Important local validation state
Before this milestone, the user confirmed:
- Full pytest: **79 passed in 7.48s**
- Focused LLM/cinematic tests: **24 passed in 0.13s**
- `qwen3:30b` installed and `tools.check_ollama --model qwen3:30b`: **PASS**

The new production-intelligence changes were committed through GitHub, but this ChatGPT session cannot execute the user's Windows Python environment. The final commands below must be run locally to verify the new code before any full-book enhance run.

### Required final validation sequence
1. Pull `llm-local-qwen` locally.
2. Run `python -m compileall -q core tests`.
3. Run `python -m pytest -q`.
4. Run focused cinematic/intent tests.
5. Run `python -m tools.check_ollama --model qwen3:30b`.
6. Generate one scene with `shadow` and inspect all three exported `.txt` files.
7. Only after the one-scene manual review passes, run the complete 191-scene pipeline.

### Runtime settings
```powershell
$env:SOCIAL_AUTOMATION_LLM_MODE="shadow"
$env:SOCIAL_AUTOMATION_LLM_MODEL="qwen3:30b"
$env:SOCIAL_AUTOMATION_LLM_TIMEOUT="1800"
$env:SOCIAL_AUTOMATION_LLM_THINK="false"
$env:SOCIAL_AUTOMATION_LLM_CONTEXT="4096"
```

### Quality gates
- Do not downgrade from `qwen3:30b` for speed.
- Do not weaken strict source validation.
- Do not start the full 191-scene `enhance` run until local tests and one-scene visual review pass.
- Image, Short Video, and Long Video must share generation intent rather than independently inventing scene interpretation.
