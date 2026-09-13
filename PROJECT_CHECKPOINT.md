## Social Automation Project Checkpoint — 2026-09-13

### Current milestone: Local LLM runtime validated — Qwen3 30B no-think inference completes

All LLM work remains isolated on `llm-local-qwen`; original `main` is untouched.

### User-confirmed local validation — today
- Full pytest: **79 passed in 7.48s**
- Focused LLM/cinematic tests: **24 passed in 0.13s**
- `qwen3:30b` installed locally
- `tools.check_ollama --model qwen3:30b`: **PASS**
- Qwen3 30B semantic inference with `SOCIAL_AUTOMATION_LLM_THINK=false` completed on Scene 2 within the 1800s timeout.
- This confirms the local Qwen runtime is usable on the current laptop when hidden thinking is disabled for this structured semantic extraction stage.

### Scene 2 LLM result — latest
The latest Scene 2 run used:
- model: `qwen3:30b`
- mode: `shadow`
- timeout: `1800s`
- thinking: `false`
- context: `4096`
- output written directly as UTF-8 with `--output`

The model returned `llm_used=true`, but the semantic result was **rejected by the existing strict source-grounding validator** (`source_validated=false`).

Observed rejection categories included:
- visual-moment evidence/text not matching the exact scene source span
- dialogue not verbatim source
- source-fact evidence not matching the exact scene source span
- names/entities such as **Ravana, Rama, Meghanada, jackals, and rats** were returned without matching scene-local canonical evidence

### Important architectural decision — DO NOT weaken the validator
The validator must remain strict and unchanged.

Story/world knowledge is a separate concern from scene-local source evidence. A character, creature, object, relationship, or other entity can legitimately belong to the broader story even when its name is absent from the extracted text of a particular scene.

Therefore:
- Do **not** remove or relax exact source-evidence validation.
- Do **not** treat valid story/world entities as hallucinations merely because they are absent from one scene's text.
- Future work should improve the knowledge/context supplied to the LLM so it can distinguish **story/world knowledge** from **scene-local evidence**.
- Scene visibility/presence still requires appropriate scene evidence; global story knowledge must not silently create physical presence in a scene.

### Current generation architecture
```text
PDF / Book
  ↓
Docling
  ↓
SQLite canonical store
  ↓
Sections → Stories → Scenes
  ↓
Entities / Characters / Locations / Events
  ↓
Character candidate gate / identity normalization / canonical characters
  ↓
Visual Knowledge Bible
  ↓
Canonical Visual Bible
  ↓
Scene visual state / continuity
  ↓
Generation Context + World & Knowledge Intelligence
  ↓
Local Qwen3 30B semantic interpretation (shadow/enhance)
  ↓
Strict source validation
  ↓
Generation Planner
  ↓
Unified Media Prompt Compiler
  ↓
 ┌─────────────┬────────────────┬────────────────┐
 │    IMAGE    │  SHORT VIDEO   │   LONG VIDEO   │
 │    PROMPT   │    CLIPS       │    SHOTS       │
 └─────────────┴────────────────┴────────────────┘
```

### User's immediate next objective
**Stop investigating the LLM runtime for now. Produce the three generation prompts for one selected scene and test them manually in an AI generator.**

The three outputs to review are:
1. **Image prompt**
2. **Short-video prompt package**
3. **Long-video prompt package**

Audio remains supporting material for video generation and is not a fourth primary prompt type.

### Important testing rule
Do not enable full-book `enhance` yet. First manually review one scene's three generated prompts and judge the actual visual/video quality in an external AI generator.

### Next engineering step after manual visual test
Use the user's visual feedback from the three generated outputs to decide what prompt-composition changes are actually needed. Preserve the strict validator while improving world/story knowledge handling separately.

### Existing runtime settings
```powershell
$env:SOCIAL_AUTOMATION_LLM_MODE="shadow"
$env:SOCIAL_AUTOMATION_LLM_MODEL="qwen3:30b"
$env:SOCIAL_AUTOMATION_LLM_TIMEOUT="1800"
$env:SOCIAL_AUTOMATION_LLM_THINK="false"
$env:SOCIAL_AUTOMATION_LLM_CONTEXT="4096"
```

### Verified tests
```text
python -m pytest -q
79 passed in 7.48s

python -m pytest tests\test_llm_runtime_hardening.py tests\test_scene_semantic_llm.py tests\test_cinematic_generation.py -q
24 passed in 0.13s

python -m tools.check_ollama --model qwen3:30b
OLLAMA CHECK: PASS
```

### Do not forget
- Original `main` remains untouched.
- Keep quality-first `qwen3:30b`; do not downgrade to 8B/14B merely for speed.
- Do not weaken the validator to accommodate LLM output.
- Do not start the full 191-scene `enhance` run before the manual three-prompt visual test is reviewed.
