# Image generation pipeline

The image pipeline consumes the authoritative all_prompts.json package produced by core.prompt_export.

It uses a visible normal Google Chrome session and Google AI Mode at https://www.google.com/ai. It does not use private Google APIs, hidden generation endpoints, CAPTCHA bypasses, stealth fingerprints, or extracted authentication cookies.

The workflow is resumable. SQLite stores scene status, attempts, prompt paths, generated paths, validation paths, and errors.

Validation is intentionally tolerant because the prompts are already refined:
- corrupted/tiny images are hard failures;
- OCR is advisory and confirms required dialogue when possible;
- optional local Qwen2.5-VL checks visual/story/continuity semantics;
- semantic retry happens only for a clear low-confidence contradiction;
- uncertain or unavailable vision validation does not fail a scene.

The first pilot should use --limit 10. If Google asks for normal sign-in, consent, CAPTCHA, or an account usage-limit action, the pipeline stops rather than attempting to bypass the control. Complete the normal user action and rerun.

Completed scenes are skipped on subsequent runs.
