## Cinematic Generation Intelligence — 2026-09-11

### Completed
- Added `core/cinematic_generation.py` as a dedicated scene-level cinematic composition layer between generation context/media compilation and final generation-plan output.
- Integrated it into `core/generation_planner.py`; generation plans now receive the cinematic enhancement before image, short-video, and long-video prompts are exported.
- Scene interpretation now separates source-anchored visual moments from controlled production inference.
- Added source-text dialogue extraction with quote-first behavior and a conservative first-person/speech-cue fallback so useful source dialogue is not discarded merely because OCR/formatting omitted quotation marks.
- Added character-specific blocking derived only from that character's scene mentions; when source does not establish exact blocking, the prompt says so rather than inventing it.
- Added deterministic cinematic direction: framing, lens/perspective, camera height, lighting, and movement style chosen from source signals such as destruction, combat, travel, dialogue, or character presence.
- Added scene-specific visual hierarchy and environment-first guidance so locations materially present in the source are not reduced to generic portraits.
- Added cinematic direction to short-video clips and long-video shots while preserving source events, identity anchors, spatial continuity, and unknown attributes.
- Changed image overlays so available source dialogue/first-person source sentences are preferred; when no dialogue is supportable, the overlay uses a source visual moment rather than blindly using the scene title.
- Strengthened prompt-export QA to require scene interpretation and cinematic direction in generated image/video prompts.
- Added `tests/test_cinematic_generation.py` regression coverage for destruction-scene direction, source sentence overlays, character-specific blocking, and propagation to video prompts.

### Export hardening
- Per-scene files use globally unique `scene_id`, not story-local `scene_order`.
- Export now removes prior `image`, `short_video`, and `long_video` directories before regeneration so stale files cannot inflate or corrupt file counts.
- Per-scene files include source database path, scene ID/order, title, and pages.
- Expected Asura output remains exactly **191 image + 191 short-video + 191 long-video files**.

### Quality target
The generation pipeline is moving from a generic prompt template toward a cinematic-generation intelligence stack:
```text
SOURCE TEXT
  -> source-anchored scene interpretation
  -> primary visual moment
  -> character-specific blocking
  -> source-derived environment/object state
  -> continuity + identity anchors
  -> controlled camera / lens / lighting / movement inference
  -> deterministic dialogue/narrative overlay
  -> generator-ready image / short-video / long-video prompts
```

Source evidence controls **what exists**. Cinematic inference controls **how it is photographed/staged**. Unsupported facts remain unknown.

### Validation required next
Sync and run:
```powershell
git pull origin main
python -m pytest -q
python -m core.dod "data\Asura\Asura - Tale Of The Vanquished.pdf"
python -m core.prompt_quality_audit "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\all_prompts.json" --sample-count 8
```

Then verify the media file counts:
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

Generation Intelligence QA confirmed the emitted Asura package is structurally valid, but representative samples exposed split identity variants such as `Lord Shiva`, `Lord Shiva Pasupathi`, and `Lord Shiva Pasupathi Literally`.

### Validation findings
- Baseline before identity tightening: **18 confirmed + 7 singleton = 25 canonical characters**.
- After the initial identity/gate tightening: **9 confirmed + 4 singleton = 13 canonical characters**.
- The 13-character DOD still passed structural QA, but the large drop was treated as a quality regression rather than accepted as correct.
- Prompt-quality audit remained **191 scenes, 0 failures, 0 observations**; this audit is structural/propagation-oriented and does not establish that the character inventory is complete.
- Local full pytest before the cinematic-generation changes was **54 passed**.

### Root cause addressed
The candidate gate had a cross-type collision protection for character candidates that could accidentally use speech/action evidence from the surrounding context as evidence for the colliding name itself. That could let a place such as `Mithila` survive as a character when another character in the same context was speaking or acting.

### Current character-gate fix
- `core/character_candidate_gate.py`
  - A character/location or character/environment collision is rejected when the **candidate name itself has no direct person evidence**.
  - Direct person evidence still allows a legitimate character to survive a cross-type collision.
  - This keeps the protection conservative without deleting valid characters merely because a place or concept shares the same normalized name.
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
