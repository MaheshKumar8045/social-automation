## Social Automation Project Checkpoint — 2026-09-14

### Current milestone: Production media-generation intelligence hardened

All work remains isolated on `llm-local-qwen`; original `main` is untouched.

### Implemented
- Local Qwen3 30B runtime integration remains available in shadow/enhance modes.
- Strict source-grounding validation remains unchanged.
- Added `core/generation_intent.py` as the shared source of truth for Image, Short Video, and Long Video.
- Visual moments are selected from complete source sentences or exact source fragments; event fragments are extended to sentence boundaries when possible and discarded when they cannot be completed from source.
- Visible character blocking now requires scene-local source evidence. Story/world references and stale mention contexts cannot silently create on-screen characters.
- First-person narration is separated from spoken dialogue and is not automatically staged as on-screen speech.
- Image planning selects a scene-signal-aware dominant composition: action for combat, consequence for destruction, movement for travel, reaction only when a visible character is actually established, otherwise environmental establishment.
- Short Video uses three progressive beats with distinct camera grammar, source focus, transitions, and synchronized dialogue/narration metadata.
- Long Video uses a dynamic 4–8 shot plan with purpose-aware camera grammar, source-moment allocation, continuity instructions, and per-shot timing. It no longer forces a character composition when no character is source-confirmed.
- Audio distinguishes spoken dialogue, first-person narration/voice-over, and no-source-dialogue cases; `dialogue_source` is aligned with actual rendered voice text.
- Shared generation intent is embedded in the media package for cross-media consistency.
- Added production regression tests, including sentence completeness, source-local character presence, cinematic progression, camera diversity, audio alignment, and intent propagation.
- Added GitHub Actions compile/test workflow.

### Validator decision
The strict validator was **not** weakened. Scene-local evidence and broader story/world knowledge remain separate layers.

### Current branch
- `llm-local-qwen` contains the complete implementation.
- `main` remains untouched.

### Local verification requirement
The prior local baseline was 79 tests passing and Ollama `qwen3:30b` health-check passing. The final hardening commits were made through GitHub and must be compiled/tested in the user's Windows environment before production generation.

### Final quality gate
1. Pull the final branch.
2. Compile all Python sources.
3. Run the full pytest suite.
4. Run focused generation/cinematic/LLM tests.
5. Run the Qwen3 30B Ollama health check.
6. Generate and inspect one production scene's Image, Short Video, and Long Video `.txt` files.
7. Run the full 191-scene shadow pipeline.
8. Only after shadow output is accepted, run enhance.

### Runtime settings
```powershell
$env:SOCIAL_AUTOMATION_LLM_MODE="shadow"
$env:SOCIAL_AUTOMATION_LLM_MODEL="qwen3:30b"
$env:SOCIAL_AUTOMATION_LLM_TIMEOUT="1800"
$env:SOCIAL_AUTOMATION_LLM_THINK="false"
$env:SOCIAL_AUTOMATION_LLM_CONTEXT="4096"
```
