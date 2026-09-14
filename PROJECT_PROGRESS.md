# Project Progress — Production Media Generation Intelligence

## Completed
- Local Qwen3 30B runtime integration in `shadow`/`enhance` modes.
- Strict source-grounding validation retained.
- Character identity/candidate gating and visual-bible continuity retained.
- Added shared `GenerationIntent` (`core/generation_intent.py`).
- Reworked cinematic generation so Image, Short Video, and Long Video share the same source-derived scene intent.
- Source visual moments are complete source sentences and are rejected from planning when they are not present in scene text.
- Character presence is explicitly split into visible vs referenced-only.
- First-person narration is not automatically treated as on-screen speech.
- Image planning now prioritizes a single dominant source moment and environment when character presence is not established.
- Short Video now follows a three-beat cinematic progression with distinct camera movement and transitions.
- Long Video now uses a dynamic 4–8 shot plan with distinct purposes, camera grammar, continuity instructions, and per-shot timing.
- Audio metadata is aligned with actual clip/shot voice text and distinguishes dialogue from narration.
- Added production-focused regression tests and GitHub Actions compile/test workflow.

## Verification status
Previously verified locally by the user: 79 tests passed, focused LLM/cinematic tests passed, and Ollama Qwen3 30B health check passed.

The production-intelligence commits were made remotely because the Windows local repository is not executable from this session. Therefore, the new code must be locally compiled/tested before production generation.

## Next commands
```powershell
git switch llm-local-qwen
git pull --ff-only origin llm-local-qwen
python -m compileall -q core tests
python -m pytest -q
python -m pytest tests\test_generation_intent.py tests\test_cinematic_generation.py tests\test_prompt_export.py tests\test_llm_runtime_hardening.py tests\test_scene_semantic_llm.py -q
python -m tools.check_ollama --model qwen3:30b
```

Then generate one scene in shadow mode and inspect:
- `image\scene_XXX.txt`
- `short_video\scene_XXX.txt`
- `long_video\scene_XXX.txt`

Only after the one-scene manual visual check passes should the full 191-scene run be started.
