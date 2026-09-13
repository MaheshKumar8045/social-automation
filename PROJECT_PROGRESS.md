# Project Progress — 2026-09-13

## Where we are
The local-LLM branch is `llm-local-qwen`. The original `main` branch is untouched.

### Latest verified state
- Full tests: **79 passed in 7.48s**
- Focused LLM/cinematic tests: **24 passed in 0.13s**
- Ollama health/model check for `qwen3:30b`: **PASS**
- Qwen3 30B inference: **completed for Scene 2 with thinking disabled**
- Scene 2 LLM result: `llm_used=true`, but `source_validated=false` because the strict validator rejected unsupported exact scene evidence.

## Important decision
**Do not change or weaken the validator.**

Global story/world knowledge and scene-local source evidence are different layers. Valid story entities may be absent from a particular scene's extracted PDF text. Improve knowledge/context handling rather than relaxing source validation.

## Immediate next task
Stop runtime investigation. Generate the three prompts for one scene and manually test them in an AI generator:

1. Image prompt
2. Short-video prompt package
3. Long-video prompt package

Audio is supporting video generation, not a fourth primary prompt.

## After the manual test
Collect visual/video feedback and then make targeted prompt-composition improvements. Do not start the full 191-scene `enhance` run until the one-scene output is visually reviewed.

## Local LLM configuration used for the latest successful inference
```powershell
$env:SOCIAL_AUTOMATION_LLM_MODE="shadow"
$env:SOCIAL_AUTOMATION_LLM_MODEL="qwen3:30b"
$env:SOCIAL_AUTOMATION_LLM_TIMEOUT="1800"
$env:SOCIAL_AUTOMATION_LLM_THINK="false"
$env:SOCIAL_AUTOMATION_LLM_CONTEXT="4096"
```

## Key architecture
```text
PDF → Docling → SQLite → sections/stories/scenes
→ entities/characters/events → identity + visual bible + continuity
→ world/knowledge context → Qwen3 30B semantic interpretation
→ strict source validation → generation planner
→ unified media prompt compiler
→ IMAGE + SHORT VIDEO + LONG VIDEO
```
