## Social Automation Project Checkpoint — 2026-09-13

### Current milestone: Local LLM runtime hardening — quality-first Qwen3 30B

All LLM work remains isolated on `llm-local-qwen`; original `main` is untouched.

### User-confirmed local validation
- Full pytest: **76 passed**
- Focused LLM/cinematic tests: **21 passed**
- `qwen3:30b` installed locally
- `tools.check_ollama --model qwen3:30b`: **PASS**
- First full Asura shadow run completed in about **1h 18m** for 191 scenes, but its Qwen semantic calls timed out; this must not be treated as successful LLM semantic interpretation.

### Scene 2 finding
Scene 2 generation completed, but the actual LLM semantic result was rejected because `qwen3:30b` timed out after **1800 seconds** even with a 30-minute timeout. The model is installed and Ollama health checks pass, so the remaining issue is inference/runtime efficiency rather than installation.

### Quality-first runtime decisions
- Keep **`qwen3:30b`** as the primary model; do not downgrade to 8B/14B merely for speed.
- The semantic extraction call now explicitly controls Qwen thinking through `SOCIAL_AUTOMATION_LLM_THINK`.
- Default thinking is **disabled for semantic extraction**. This does **not** change the model: Qwen3 30B remains the semantic engine, while hidden chain-of-thought is unnecessary for a tightly source-constrained structured extraction and can consume the inference budget.
- Set `SOCIAL_AUTOMATION_LLM_THINK=true` when deeper reasoning is explicitly desired.
- Default per-scene Ollama timeout is **1800 seconds (30 minutes)** and remains configurable with `SOCIAL_AUTOMATION_LLM_TIMEOUT`.
- Context defaults to **4096 tokens** and is configurable with `SOCIAL_AUTOMATION_LLM_CONTEXT`.

### Changes now committed on `llm-local-qwen`
- `core/ollama_client.py`
  - quality-first `qwen3:30b` default
  - default timeout 1800s
  - explicit thinking control, default off for semantic extraction
  - explicit 4096-token context default
  - timeout errors report the configured duration
- `core/generation_planner.py`
  - shadow mode is observation-only: LLM semantics cannot mutate production media prompts
  - only `enhance` mode can apply a source-validated ready LLM result
  - truncated source visual fragments are extended to the next real source sentence boundary
  - image prompt receives explicit dialogue-or-narrative safe-area instruction when missing
  - progress is written to **stderr**, keeping stdout machine-readable
  - `--output` writes planner JSON directly as UTF-8, avoiding PowerShell UTF-16 redirection
- `core/dod.py`
  - computes scene total and enables automatic progress reporting
  - supports LLM timeout and thinking controls
- `tests/test_llm_runtime_hardening.py`
  - timeout, thinking-mode, context, validation, and source-fragment regressions
- `requirements.txt`
  - aligns the tracked Windows dependency versions with the validated local environment and includes `ollama==0.6.2`

### Required local validation next
1. Pull the latest `llm-local-qwen` branch.
2. Run `pip check` and the full pytest suite.
3. Run the Ollama health/model check.
4. Run **Scene 2 only** with `SOCIAL_AUTOMATION_LLM_THINK=false` using the explicit UTF-8 `--output` option.
5. Review the returned semantic result and runtime.
6. If Scene 2 is still too weak, repeat Scene 2 with `SOCIAL_AUTOMATION_LLM_THINK=true` as the quality comparison.
7. Only if Scene 2 returns `status=ready`, `llm_used=true`, and `source_validated=true`, run a controlled `enhance` test on Scene 2.
8. Only after the controlled enhance output is accepted should the full 191-scene enhance run begin.

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
$env:SOCIAL_AUTOMATION_LLM_TIMEOUT="1800"
$env:SOCIAL_AUTOMATION_LLM_THINK="false"
$env:SOCIAL_AUTOMATION_LLM_CONTEXT="4096"
python -m core.generation_planner "data\Asura\Asura - Tale Of The Vanquished_structure.db" 1 2 --output scene2_after_hardening.json
python -c "import json; d=json.load(open('scene2_after_hardening.json',encoding='utf-8')); print(json.dumps(d.get('llm_scene_semantics',{}),indent=2,ensure_ascii=False))"
```

Do not start the full-book `enhance` run until the Scene 2 semantic result is genuinely `ready` and source validated and the resulting media prompts have been reviewed.
