## Cinematic Generation Intelligence — 2026-09-11

### Completed
- Added `core/cinematic_generation.py` as a dedicated scene-level cinematic composition layer between generation context/media compilation and final generation-plan output.
- Integrated it into `core/generation_planner.py`; generation plans now receive the cinematic enhancement before image, short-video, and long-video prompts are exported.
- Scene interpretation separates source-anchored visual moments from controlled production inference.
- Added source-text dialogue extraction with quote-first behavior and a conservative first-person/speech-cue fallback.
- Hardened dialogue extraction against OCR contamination: section/chapter prefixes and likely speaker-name prefixes are removed before first-person dialogue is accepted.
- Character presence is now split into `visible` versus `referenced`; a name-only reference is never automatically rendered as a visible character.
- Visible character blocking requires physical/presence evidence from that character's own scene mention context or a matching scene event.
- Matching scene-event text is preferred over abbreviated mention snippets when establishing visible character blocking, preserving the canonical event wording.
- Referenced-but-not-visually-established characters are retained as semantic metadata so they remain traceable without contaminating the image composition.
- Added deterministic cinematic direction: framing, lens/perspective, camera height, lighting, and movement style chosen from source signals such as destruction, combat, travel, dialogue, or character presence.
- Added scene-specific visual hierarchy and environment-first guidance so locations materially present in the source are not reduced to generic portraits.
- Added cinematic direction to short-video clips and long-video shots while preserving source events, identity anchors, spatial continuity, and unknown attributes.
- Image overlays prefer supportable source dialogue; when no dialogue is supportable, the overlay uses a source visual moment rather than blindly using the scene title.
- Strengthened prompt-export QA to require scene interpretation and cinematic direction in generated image/video prompts.
- Added regression coverage for OCR heading/speaker contamination, name-only character references, physical-presence requirements, and event-vs-mention character blocking.

### Regression correction — 2026-09-11
- Local pytest after the first semantic patch reported **61 passed, 2 failed**.
- Failure 1 was caused by dialogue cleanup treating the legitimate first-person `I` as an OCR speaker-prefix token. The cleanup now preserves first-person pronouns.
- Failure 2 was caused by character blocking using the abbreviated mention `my son captured Kumbha.` instead of the canonical scene event `Kumbha was captured by my son.`. Blocking now prefers a matching event text when it establishes physical/action evidence.
- These regressions were fixed in commit `28212b49064f60e4003fc78d6964ccc1f10f615f`.
- The next required validation is a fresh local full pytest run; no test pass is claimed until that run completes.

### Export hardening
- Per-scene files use globally unique `scene_id`, not story-local `scene_order`.
- Export removes prior `image`, `short_video`, and `long_video` directories before regeneration so stale files cannot inflate or corrupt file counts.
- Per-scene files include source database path, scene ID/order, title, and pages.
- Expected Asura output remains exactly **191 image + 191 short-video + 191 long-video files**.

### Quality target
The generation pipeline is now structured as:
```text
SOURCE TEXT
  -> source-anchored scene interpretation
  -> primary visual moment
  -> visible-vs-referenced character decision
  -> character-specific blocking where physically established
  -> source-derived environment/object state
  -> continuity + identity anchors
  -> controlled camera / lens / lighting / movement inference
  -> deterministic dialogue/narrative overlay
  -> generator-ready image / short-video / long-video prompts
```

Source evidence controls **what exists**. Cinematic inference controls **how established content is photographed/staged**. Unsupported facts remain unknown.

### Validation required next
Run locally after pulling the latest commits:
```powershell
git pull origin main
python -m pytest -q
python -m core.dod "data\Asura\Asura - Tale Of The Vanquished.pdf"
python -m core.prompt_quality_audit "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\all_prompts.json" --sample-count 8
```

Verify the media file counts:
```powershell
(Get-ChildItem "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\image" -Filter *.txt).Count
(Get-ChildItem "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\short_video" -Filter *.txt).Count
(Get-ChildItem "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\long_video" -Filter *.txt).Count
```
Expected:
```text
191
191
191
```

### Scene-level review
Open any one scene independently:
```powershell
notepad "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\image\scene_001.txt"
notepad "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\short_video\scene_001.txt"
notepad "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\long_video\scene_001.txt"
```
The image file contains the image prompt, layout constraints, and deterministic text overlays. The short-video file contains all clips plus audio direction. The long-video file contains all shots plus audio direction.

### Character Identity QA — 2026-09-11

Generation Intelligence QA previously exposed split identity variants such as `Lord Shiva`, `Lord Shiva Pasupathi`, and `Lord Shiva Pasupathi Literally`, and a false-positive `Mithila` character in a location collision case.

### Character-gate fixes
- `core/character_candidate_gate.py`
  - A character/location or character/environment collision is rejected when the **candidate name itself has no direct person evidence**.
  - Direct person evidence still allows a legitimate character to survive a cross-type collision.
  - Tests cover strong person evidence surviving a location collision, location-only evidence being rejected, and unrelated contextual speech/action not validating the colliding name.

### Current repository state
- Repository: `MaheshKumar8045/social-automation`
- Branch: `main`
- Real Asura DB:
  `data\Asura\Asura - Tale Of The Vanquished_structure.db`
- Confirmed SQLite schema includes `documents`, `entities`, `entity_mentions`, `canonical_characters`, `mention_identity_resolution`, visual tables, and related pipeline tables.
- Local environment uses `M:\social-automation\.venv\Scripts\python.exe`.

### Known separate quality item
Docling still reports noisy OCR/recovered headings and 63 final sections despite numbered headings reaching 65. DOD is not blocked, but section reconciliation remains a separate quality item before section extraction is treated as final ground truth.
