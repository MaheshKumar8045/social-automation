## Media Prompt Export — 2026-09-11

### Completed
- Fixed the character-candidate location/environment collision bug so unrelated speech/action evidence cannot validate a colliding name.
- Added regression coverage for direct person evidence versus location-only evidence.
- Local full test suite before export fix: **54 passed**.
- Added copy-friendly per-scene media prompt export to `core/prompt_export.py`.
- Diagnosed and fixed a filename collision in that exporter: `scene_order` restarts inside each story, so using it as the filename caused later stories to overwrite earlier files and left only the last few files visible.
- Per-scene media filenames now use the globally unique `scene_id`.
- Each generated scene gets its own text file in three dedicated folders:
  - `image/scene_001.txt` … one file per scene for image generation, including the image prompt, layout constraints, and dialogue/narrative overlay data.
  - `short_video/scene_001.txt` … one file per scene containing all short-video clips plus audio direction.
  - `long_video/scene_001.txt` … one file per scene containing all long-video shots plus audio direction.
- Existing aggregate outputs remain unchanged: `all_prompts.json`, `scene_prompts.jsonl`, and `prompt_export_summary.json`.

### Expected real Asura output
The source package contains **191 scenes**. A clean DOD run after syncing this fix should therefore produce **191 image files + 191 short-video files + 191 long-video files**, one per scene, with no overwriting from repeated story-local scene ordering.

### Output layout
```text
<data stem>_prompts/
  all_prompts.json
  scene_prompts.jsonl
  prompt_export_summary.json
  image/
    scene_001.txt
    scene_002.txt
    ...
    scene_191.txt
  short_video/
    scene_001.txt
    scene_002.txt
    ...
    scene_191.txt
  long_video/
    scene_001.txt
    scene_002.txt
    ...
    scene_191.txt
```

### Required validation
After syncing `main`, run:
```powershell
git pull origin main
python -m pytest -q
python -m core.dod "data\Asura\Asura - Tale Of The Vanquished.pdf"
python -m core.prompt_quality_audit "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\all_prompts.json" --sample-count 8
```

Then verify file counts:
```powershell
(Get-ChildItem "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\image" -Filter *.txt).Count
(Get-ChildItem "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\short_video" -Filter *.txt).Count
(Get-ChildItem "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\long_video" -Filter *.txt).Count
```
Each count should be **191**.

### Character Identity QA — 2026-09-11

Generation Intelligence QA confirmed the emitted Asura package is structurally valid, but representative samples exposed split identity variants such as `Lord Shiva`, `Lord Shiva Pasupathi`, and `Lord Shiva Pasupathi Literally`.

### Validation findings
- Baseline before identity tightening: **18 confirmed + 7 singleton = 25 canonical characters**.
- After the initial identity/gate tightening: **9 confirmed + 4 singleton = 13 canonical characters**.
- The 13-character DOD still passed structural QA, but the large drop was treated as a quality regression rather than accepted as correct.
- Prompt-quality audit remained **191 scenes, 0 failures, 0 observations**; this audit is structural/propagation-oriented and does not establish that the character inventory is complete.
- Latest local pytest before the export filename fix: **54 passed**.

### Root cause addressed
The candidate gate had a cross-type collision protection for character candidates that could accidentally use speech/action evidence from the surrounding context as evidence for the colliding name itself. That could let a place such as `Mithila` survive as a character when another character in the same context was speaking or acting.

### Current fix
- `core/character_candidate_gate.py`
  - A character/location or character/environment collision is rejected when the **candidate name itself has no direct person evidence**.
  - Direct person evidence still allows a legitimate character to survive a cross-type collision.
  - This keeps the protection conservative without deleting valid characters merely because a place or concept shares the same normalized name.
- `tests/test_character_candidate_gate.py`
  - Covers strong person evidence surviving a location collision.
  - Covers weak location-only evidence being rejected.
  - Includes the regression needed to prevent unrelated contextual speech/action cues from being treated as evidence for the colliding name.
- `core/character_identity_normalizer.py`
  - Retains conservative qualified-name matching for titled identity prefixes with short epithet suffixes.
- `tests/test_character_identity_qualifiers.py`
  - Covers `Lord Shiva` / qualified variants and keeps `Lord Shiva` distinct from `Lord Vishnu`.

### Current repository / validation state
- Repository: `MaheshKumar8045/social-automation`
- Branch: `main`
- Real Asura DB:
  `data\Asura\Asura - Tale Of The Vanquished_structure.db`
- Confirmed SQLite schema includes `documents`, `entities`, `entity_mentions`, `canonical_characters`, `mention_identity_resolution`, visual tables, and related pipeline tables.
- Local environment uses `M:\social-automation\.venv\Scripts\python.exe`.

### Prompt review / generation inspection
The generated package now has three copy-friendly per-scene media folders:
- `image\scene_###.txt`
- `short_video\scene_###.txt`
- `long_video\scene_###.txt`

Each file is scoped to one scene. Image files contain the image prompt plus layout/overlay guidance. Short-video files contain all clips for that scene plus audio direction. Long-video files contain all shots for that scene plus audio direction.

The aggregate `all_prompts.json` remains the authoritative machine-readable package.

### What the next review should check
1. Three media directories each contain exactly 191 files for the Asura source.
2. Canonical-character count versus the prior 25-character baseline.
3. `Lord Shiva` variants sharing one `identity_anchor`.
4. No `Who`, `Mithila`, or similar place/common names becoming canonical characters.
5. Character-free scenes remaining character-free only where source evidence supports it.
6. Image prompts being concrete enough for generation while preserving source-grounded facts and clearly separating inference.
7. Short-video clips and long-video shots being sufficiently specific for actual video generation rather than generic descriptions.
8. Deterministic overlays/dialogue and audio guidance staying subordinate to the primary visual moment.
9. World profile remaining contextual guidance rather than fabricated source facts.

### Known separate quality item
Docling still reports noisy OCR/recovered headings and 63 final sections despite numbered headings reaching 65. DOD is not blocked, but section reconciliation remains a separate quality item before section extraction is treated as final ground truth.
