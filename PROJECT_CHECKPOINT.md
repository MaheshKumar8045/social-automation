## Social Automation Project Checkpoint — 2026-09-14

### Current milestone: Production media-generation intelligence hardened

All work remains isolated on `llm-local-qwen`; original `main` is untouched.

### Implemented
- Local Qwen3 30B runtime integration remains available in shadow/enhance modes.
- Strict source-grounding validation remains unchanged.
- Added `core/generation_intent.py` as the shared source of truth for Image, Short Video, and Long Video.
- Visual moments are selected from complete source sentences or exact source fragments; event fragments are extended to sentence boundaries when possible and discarded when they cannot be completed from source.
- When no validated event candidates exist, source sentences retain source order instead of being arbitrarily reordered.
- Visible character blocking now requires scene-local physical evidence using character-presence verbs/actions, not generic scene words such as `battle`; story/world references and stale mention contexts cannot silently create on-screen characters.
- First-person narration is separated from spoken dialogue and is not automatically staged as on-screen speech.
- Image planning selects a scene-signal-aware dominant composition: action for combat, consequence for destruction, movement for travel, reaction only when a visible character is actually established, otherwise environmental establishment.
- Short Video uses three progressive beats from the shared cinematic arc with distinct camera grammar, source focus, transitions, and synchronized dialogue/narration metadata.
- Long Video uses a dynamic 4–8 shot plan with purpose-aware camera grammar, source-moment allocation, continuity instructions, and per-shot timing. It no longer forces a character composition when no character is source-confirmed.
- Audio distinguishes spoken dialogue, first-person narration/voice-over, and no-source-dialogue cases; `dialogue_source` is aligned with actual rendered voice text.
- Every cinematic prompt explicitly labels `SOURCE VISUAL MOMENT` in addition to `SOURCE-ANCHORED SCENE INTERPRETATION`.
- Camera schema handling is tolerant of the internal `camera_height`/`height` representation so prompt generation cannot fail on a key mismatch.
- `core/ocr_engine.py` now lazy-loads PaddleOCR/NumPy so lightweight test imports do not require the GPU OCR stack; production OCR behavior is unchanged when `OCREngine` is instantiated.
- CI test dependencies include the lightweight runtime packages required by the test import graph (`pydantic`, `ollama`, `pypdf`, `pillow`).
- Added production regression tests, including sentence completeness, source-local character presence, cinematic progression, camera diversity, audio alignment, and intent propagation.
- Added GitHub Actions compile/test workflow with retained pytest logs for deterministic diagnosis.

### Validator decision
The strict validator was **not** weakened. Scene-local evidence and broader story/world knowledge remain separate layers.

### Current branch
- `llm-local-qwen` contains the complete implementation.
- `main` remains untouched.

### Verification history
- The previously failing hardening suite reached **89 passed, 1 failed** in CI; the remaining failure was only the expected `SOURCE VISUAL MOMENT` prompt label.
- That final prompt-contract failure has now been corrected in the latest branch commit. The newest GitHub Actions run is the final verification gate.
- Earlier local verification also established Ollama `qwen3:30b` availability and the prior baseline of 79 passing tests.

### Final quality gate
1. Pull the final branch.
2. Compile all Python sources.
3. Confirm the full pytest suite is green.
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