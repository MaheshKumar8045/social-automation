## Social Automation Project Checkpoint — 2026-09-13

### Current milestone: Local LLM runtime hardening

All LLM work remains isolated on `llm-local-qwen`; original `main` is untouched.

### User-confirmed baseline before this milestone
- Full pytest: **67 passed**
- `tests/test_scene_semantic_llm.py`: **4 passed**
- `tests/test_cinematic_generation.py`: **8 passed**
- Ollama 0.34.0 installed locally
- `qwen3:30b` installed and `tools.check_ollama` passed
- First full Asura shadow run completed in about **1h 18m** for 191 scenes

### Scene 2 review finding
Scene 2's LLM semantic result was rejected because Ollama timed out. The deterministic fallback exposed three runtime/design issues: shadow-mode mutation risk, truncated visual moments propagating into prompts, and image QA requiring an explicit dialogue/narrative-box instruction even when structured overlays existed.

### Changes now committed on `llm-local-qwen`
- `core/ollama_client.py`
  - default per-scene timeout raised from 300s to 900s
  - timeout remains configurable with `SOCIAL_AUTOMATION_LLM_TIMEOUT`
  - invalid/non-positive timeout fails fast
  - timeout errors report the configured duration
- `core/generation_planner.py`
  - plan version 9
  - shadow mode is observation-only: LLM semantics are exported but cannot mutate production media prompts
  - only `enhance` mode can apply a source-validated ready LLM result
  - truncated source visual fragments are extended to the next real source sentence boundary before export
  - image prompt receives an explicit dialogue-or-narrative safe-area instruction when missing, aligning prompt text with QA contract
  - automatic per-scene progress prints include completed/total, percentage, elapsed time, average seconds/scene and ETA
- `core/dod.py`
  - computes scene total and enables automatic progress reporting
  - adds `--llm-timeout`
- `tests/test_llm_runtime_hardening.py`
  - regressions for timeout defaults/override/validation and truncated source-fragment repair

### Git commits for this milestone
- `f1fd140fbfa42c79423b387a226e9864f135499a` planner hardening
- `536a345a3ee33332bdbc7f0146ca67064cd5c830` Ollama timeout hardening
- `0f6da7a1295121de8ee9562cdf5800a78d50fc60` DOD progress/timeout CLI
- `dbbd59c85746f247b0283f40d3163b3dbd548199` runtime hardening regressions

### Required local validation next
Pull the branch, run the full test suite, then run Scene 2 only with Qwen before another 191-scene pass. Do not enable full-book `enhance` until Scene 2 returns `status=ready`, `llm_used=true`, and `source_validated=true` and its semantic output is reviewed.

### Recommended local commands
```powershell
git checkout llm-local-qwen
git pull origin llm-local-qwen
python -m pip check
python -m pytest -q
python -m pytest tests\test_llm_runtime_hardening.py tests\test_scene_semantic_llm.py tests\test_cinematic_generation.py -q
python -m tools.check_ollama --model qwen3:30b
$env:SOCIAL_AUTOMATION_LLM_MODE="shadow"
$env:SOCIAL_AUTOMATION_LLM_MODEL="qwen3:30b"
$env:SOCIAL_AUTOMATION_LLM_TIMEOUT="900"
python -m core.generation_planner "data\Asura\Asura - Tale Of The Vanquished_structure.db" 1 2 > scene2_after_hardening.json
```

Review `scene2_after_hardening.json`. If Scene 2 is ready and source validated, proceed to a controlled enhance test for Scene 2 only before a full-book enhance run.
