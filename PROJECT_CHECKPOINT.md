## Character Identity QA — 2026-09-11

Generation Intelligence QA confirmed the emitted Asura package is structurally valid, but representative samples exposed split identity variants such as `Lord Shiva`, `Lord Shiva Pasupathi`, and `Lord Shiva Pasupathi Literally`.

### Validation findings
- Baseline before identity tightening: **18 confirmed + 7 singleton = 25 canonical characters**.
- After the initial identity/gate tightening: **9 confirmed + 4 singleton = 13 canonical characters**.
- The 13-character DOD still passed structural QA, but the large drop was treated as a quality regression rather than accepted as correct.
- Prompt-quality audit remained **191 scenes, 0 failures, 0 observations**; this audit is structural/propagation-oriented and does not establish that the character inventory is complete.
- The latest local pytest run is **54 passed**, confirming the corrected collision behavior and the full existing regression suite.

### Root cause addressed
The candidate gate had a cross-type collision protection for character candidates that could accidentally use speech/action evidence from the surrounding context as evidence for the colliding name itself. That could let a place such as `Mithila` survive as a character when another character in the same context was speaking or acting.

### Current fix
- `core/character_candidate_gate.py`
  - A character/location or character/environment collision is now rejected when the **candidate name itself has no direct person evidence**.
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
- Latest character-gate regression commits are on GitHub `main`.
- Local environment is correctly using `M:\social-automation\.venv\Scripts\python.exe`.
- `python -m pytest -q` passes: **54 passed**.
- Real Asura DB was located at:
  `data\Asura\Asura - Tale Of The Vanquished_structure.db`
- Confirmed SQLite schema includes `documents`, `entities`, `entity_mentions`, `canonical_characters`, `mention_identity_resolution`, visual tables, and related pipeline tables.

### Required validation next
Regenerate the real Asura package after syncing `main`. The corrected result should recover legitimate characters removed by the hard collision gate while still preventing place-only names from becoming canonical characters. Qualified Shiva variants should remain consolidated.

Run:
```powershell
git pull origin main
python -m pytest -q
python -m core.dod "data\Asura\Asura - Tale Of The Vanquished.pdf"
python -m core.prompt_quality_audit "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\all_prompts.json" --sample-count 8
```

### Prompt review / generation inspection
The generated package is designed to contain the three primary generation prompt families:
- image prompt
- short-video clips
- long-video shots

The same visual policy feeds all three and carries source grounding, world context, visual inference, continuity constraints, and deterministic text/audio guidance.

After DOD completes, inspect the full generated package with:
```powershell
Get-Content "data\Asura\Asura - Tale Of The Vanquished_structure_prompts\all_prompts.json" -Raw | Set-Content "data\Asura\asura_prompts_for_ai_review.txt"
```
The JSON is the authoritative machine-readable package. For an AI review, the preferred input is the generated `all_prompts.json`; the command above creates a text copy that is easy to open/copy from PowerShell. Do not treat a prompt preview as equivalent to the full package.

### What the next review should check
1. canonical-character count versus the prior 25-character baseline;
2. `Lord Shiva` variants sharing one `identity_anchor`;
3. no `Who`, `Mithila`, or similar place/common names becoming canonical characters;
4. character-free scenes remaining character-free only where source evidence supports it;
5. image prompts being concrete enough for generation while preserving source-grounded facts and clearly separating inference;
6. short-video clips and long-video shots being sufficiently specific for actual video generation rather than generic descriptions;
7. deterministic overlays/dialogue and audio guidance staying subordinate to the primary visual moment;
8. world profile remaining contextual guidance rather than fabricated source facts.

### Known separate quality item
Docling still reports noisy OCR/recovered headings and 63 final sections despite numbered headings reaching 65. DOD is not blocked, but section reconciliation remains a separate quality item before section extraction is treated as final ground truth.

## Previous checkpoint

The World & Knowledge Intelligence v1 implementation used deterministic weighted source signal analysis, cached per document. Local pytest after classifier correction: **41 passed in 6.96s**.
