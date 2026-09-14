# Project Progress — Production Media Generation Intelligence

## Completed
- Local Qwen3 30B runtime integration in `shadow`/`enhance` modes.
- Strict source-grounding validation retained; no validator weakening.
- Character identity/candidate gating and visual-bible continuity retained.
- Shared `GenerationIntent` is now the single source-of-truth layer for Image, Short Video, and Long Video.
- Visual moments are source-traceable and sentence-complete; incomplete event fragments are extended only when the source contains the completion.
- Visible character presence requires scene-local source evidence. Broader story/world knowledge and stale mention contexts cannot create on-screen characters.
- First-person narration is explicitly separated from spoken dialogue.
- Image composition is scene-signal aware and does not force character portraits when the scene establishes only environment/action.
- Short Video uses three progressive beats with distinct camera grammar and transitions.
- Long Video uses a dynamic 4–8 shot plan with purpose-specific camera grammar and no forced character shots.
- Audio voice metadata is synchronized with the actual dialogue/narration used by clips and shots.
- Cross-media continuity is carried through the shared generation intent.
- Production regression tests cover source completeness, source-local presence, narration, cinematic progression, camera diversity, audio alignment, and shared intent.
- GitHub Actions compile/test workflow added.

## Final implementation review
Double-checked the agreed production fixes and corrected two additional risks found during review:
1. Visible character evidence could previously come from a mention context that was not present in the current scene. This is now source-local only.
2. Long-form role planning could repeat the same role/camera grammar as shot count increased. The planner now has explicit consequence/develop/destination profiles and a controlled optional-role sequence rather than cycling the first three roles.

The strict validator remains unchanged.

## Verification status
Previous local baseline verified by the user: 79 tests passed; focused LLM/cinematic tests passed; Ollama `qwen3:30b` check passed. The latest hardening commits were written through GitHub, so final execution verification must be performed locally in the Windows environment.

## Final commands
```powershell
git switch llm-local-qwen
git pull --ff-only origin llm-local-qwen
python -m compileall -q core tests
python -m pytest -q
python -m pytest tests\test_generation_intent.py tests\test_cinematic_generation.py tests\test_prompt_export.py tests\test_llm_runtime_hardening.py tests\test_scene_semantic_llm.py -q
python -m tools.check_ollama --model qwen3:30b
```

Then run one-scene generation and inspect all three media `.txt` outputs before the full 191-scene run.
