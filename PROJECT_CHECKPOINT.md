## Social Automation Project Checkpoint — 2026-09-11

### Current milestone: Cinematic Generation Intelligence QA

### Completed
- Added `core/cinematic_generation.py` as the dedicated scene-level cinematic composition layer between generation context/media compilation and final generation-plan output.
- Integrated it into `core/generation_planner.py`; image, short-video, and long-video generation plans receive the cinematic enhancement.
- Scene interpretation separates source-anchored visual moments from controlled production inference.
- Added source-text dialogue extraction with quote-first behavior and conservative first-person/speech-cue fallback.
- Hardened dialogue extraction against OCR contamination, including chapter/section prefixes and likely speaker-name prefixes.
- Character presence is split into `visible` versus `referenced`.
- A name-only character reference is never automatically rendered as a visible character.
- Visible character blocking requires physical/presence evidence tied to the character, from a matching scene event or scene mention.
- Matching scene-event text is preferred over abbreviated mention snippets for blocking, preserving canonical source wording.
- Added deterministic cinematic direction: framing, lens/perspective, camera height, lighting, and movement style selected from source signals.
- Added scene-specific visual hierarchy and environment-first guidance.
- Added cinematic direction to short-video clips and long-video shots while preserving source events, identity anchors, continuity, and unknown attributes.
- Image overlays prefer supportable source dialogue; when unavailable, they use a source visual moment rather than blindly using the scene title.
- Strengthened prompt-export QA to require scene interpretation and cinematic direction.
- Added regression coverage for OCR contamination, first-person dialogue, name-only references, physical presence, and event-vs-mention blocking.

### Latest QA result
Local full test suite is now GREEN:
```text
63 passed
```
The focused cinematic-generation suite is also GREEN:
```text
8 passed in 0.09s
```
The final remaining cinematic regression was caused by `_HEADING_PREFIX_RE` interpreting the first-person pronoun `I` as a Roman-numeral section heading. The regex was corrected in commit `db68b47dc161a8bd2763d7a14fce56c6388f2bbe`.

### Git commits for this milestone
- `da70d87877462046e92b9030e15b780b5e4f1c33` — semantic cinematic generation changes
- `f2c4772e04713481e9e7d1750df6cf71126e6e6e` — initial semantic regression tests
- `28212b49064f60e4003fc78d6964ccc1f10f615f` — fixes event-vs-mention blocking and dialogue cleanup regressions
- `961061cbde5ca0c8ffc877c7c41c34183b679dae` — follow-up cleanup regression attempt
- `db68b47dc161a8bd2763d7a14fce56c6388f2bbe` — final Roman-numeral heading regex fix; verified by the 8-test cinematic suite and then the full 63-test suite

### Current validation stage
The user is currently running the real Asura DOD locally after the 63/63 pytest pass.
Command:
```powershell
python -m core.dod "data\Asura\Asura - Tale Of The Vanquished.pdf"
```

After DOD completes, the next immediate review is **Scene 2 output quality**. Compare the generated Scene 2 against the earlier Scene 1 problems, especially:
- OCR heading/speaker text contaminating dialogue overlays
- referenced characters incorrectly rendered as visible characters
- visible character blocking tied to the wrong mention snippet
- noisy scene title presentation
- whether source-anchored visual moments remain faithful
- whether cinematic inference is clearly separated from source truth
- whether environment-led composition is preserved when the environment is the actual source moment
- whether identity anchors/continuity remain intact

The user will provide Scene 2 output for direct quality review after DOD.

### Expected Asura pipeline counts
The real Asura DOD historically produces:
- 442 pages
- 63 reconciled sections
- 63 stories
- 191 scenes
- 2078 entities
- 6463 mentions
- 2109 aliases
- 191 events
- 5140 continuity entity states
- 18 confirmed canonical characters + 7 singleton characters before identity-tightening work
- 25 visual knowledge-bible profiles
- 3 visual knowledge-bible facts
- 17 objects
- 192 object mentions
- 191 scene contexts
- 25 canonical visual-bible profiles
- 0 contradictions
- 191 image prompt files
- 191 short-video prompt files
- 191 long-video prompt files

These are expected/reference counts, not a claim about the current DOD run until its output is supplied.

### World & Knowledge Intelligence v1
- `core/world_context.py` provides a dependency-free deterministic world classifier.
- Weighted signals cover narrative type, religious context, culture, region, and period.
- Candidate labels/confidence/evidence are retained.
- Unknown dimensions remain unknown.
- `llm_used=False`.
- Results are cached per database/document.
- Specific mythology markers are weighted above generic historical terms.
- Evidence precedence is defined as: book explicit → book-derived → verified external (future) → controlled inference.
- External knowledge providers are not yet integrated.

### Visual generation policy
- `core/visual_generation_policy.py`
- `config/visual_generation_policy.json`
- `core/generation_context.py`
- `core/generation_planner.py`
- `core/media_prompt_compiler.py`
- `core/prompt_builder.py`
- `core/prompt_export.py`

Policy essentials:
- fallback genre `general_narrative`
- genre priors include mythology, historical, biography, patriotic, fantasy, crime_thriller, science_fiction
- never infer exact eye color, hair color, height, exact age, or facial measurements
- inferred attributes are locked for continuity
- primary image is mobile-first 9:16
- safe outer margin 7%
- critical safe area 86%
- background visible 35–55%
- main subject 45–65%
- secondary subject 25–50%
- group subject 30–55%
- dialogue max width 68%, max height 15%
- dialogue occupies protected negative space and avoids faces, hands, important objects, and primary action
- source dialogue is exact when supportable
- no source dialogue → narrative box from a source visual moment / scene context
- text is treated as a deterministic overlay concept
- same visual policy feeds image, short video, and long video

### Character identity / candidate gate QA
Known prior issues:
- split identity variants such as `Lord Shiva`, `Lord Shiva Pasupathi`, and `Lord Shiva Pasupathi Literally`
- false-positive `Mithila` character in a location collision
- candidate-gate cross-type collision logic previously allowed unrelated speech/action context to validate a colliding location name

Current gate rule:
- character/location or character/environment collision is rejected when the candidate name itself has no direct person evidence
- direct person evidence still allows a legitimate character to survive a collision
- tests cover direct evidence surviving a collision, location-only rejection, and unrelated speech/action not validating the colliding name

### Known separate quality item
Docling still reports noisy OCR/recovered headings and 63 final sections despite numbered headings reaching 65. Section reconciliation remains a separate quality item and should not be treated as final ground truth yet.

### Current resume point
1. Wait for the user's local Asura DOD output.
2. Review Scene 2 prompt package against the Scene 1 baseline.
3. Decide whether semantic/cinematic output is materially better before making another code change.
4. Do not refactor or expand scope based only on assumptions; use the generated Scene 2 evidence.
5. After Scene 2 review, record the next quality milestone and continue incrementally.