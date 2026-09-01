# Mahabarath — Project Status & Architecture

> **Purpose:** This is the shared daily status report and architecture baseline for the Mahabarath project. It is the first document to consult before starting work. Update it at the end of each meaningful work session/day so we do not rebuild capabilities that already exist or repeat completed exercises.
>
> **Source-of-truth rule:** Current Git `main` code/configuration and tested behavior take precedence over older milestone notes or legacy documentation.

## Status Snapshot

**Current repository baseline:** `main` — latest known working generation/prompt changes are committed in Git.

**Working principle from the project team:** Code present in Git has been tested after updates and should be treated as working unless a new regression is demonstrated.

**Windows scheduler state observed:** `SocialAutomation-Generation` exists but is currently **Disabled** on the Windows machine. This is an environment state, not evidence that the scheduler code is missing.

**Current major position:** Document ingestion, structural extraction, canonical knowledge, RAG, visual knowledge, continuity, generation planning, provider abstraction, generation queue/scheduling, asset lifecycle, and social image export are implemented. Social-platform publishing and a single consolidated new-PDF production orchestrator remain future integration work.

---

# 1. Canonical Architecture

```text
                         INPUT BOOK
                            PDF
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ A. DOCUMENT INGESTION                                           │
│                                                                 │
│ PDF inspection → native PDF text / OCR → page processing       │
│ → layout-aware fragments → deterministic normalization          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ B. DOCUMENT STRUCTURE                                           │
│                                                                 │
│ heading detection → page classification → section validation   │
│ → Roman numeral normalization → reconciliation → recovery       │
│                                                                 │
│                         FINAL SECTIONS                            │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ C. CANONICAL DOCUMENT STORE — SQLite                            │
│                                                                 │
│ documents / pages / sections / chunks                            │
│ stories / scenes                                                 │
│ entities / mentions / aliases / events                           │
│ RAG documents / FTS5                                             │
│ generation queue/jobs/assets/usage/continuity/visual state       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
               ┌───────────────┴────────────────┐
               ▼                                ▼
┌──────────────────────────────┐   ┌──────────────────────────────┐
│ D. STORY / SCENE LAYER       │   │ E. ENTITY LAYER              │
│                              │   │                              │
│ Section → Story → Scene      │   │ Character                    │
│ Source-grounded segmentation │   │ Location                     │
│ Page/source provenance        │   │ Environment                  │
│                              │   │ Event                        │
└──────────────┬───────────────┘   └──────────────┬───────────────┘
               │                                  │
               └────────────────┬─────────────────┘
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ F. CHARACTER IDENTITY / CANONICALIZATION                        │
│                                                                 │
│ raw candidates → candidate gate → identity evidence             │
│ → mention identity resolution → canonical characters             │
│                                                                 │
│ Conservative statuses: confirmed / likely / singleton / etc.    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ G. RAG / RETRIEVAL                                              │
│                                                                 │
│ sections + stories + scenes + pages + chunks + entities/events  │
│ → SQLite FTS5 / BM25 → source-grounded retrieval                │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ H. VISUAL KNOWLEDGE BIBLE                                       │
│                                                                 │
│ canonical characters → visual profiles → visual facts           │
│ → reconciliation → conflict classification → props/objects      │
│ → scene visual context                                           │
│                                                                 │
│ Every fact retains evidence/provenance/confidence.              │
│ Unsupported appearance remains UNKNOWN.                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ I. VISUAL CONTINUITY                                            │
│                                                                 │
│ character presence + appearance + clothing + condition          │
│ + emotional state + persistent objects + environment state      │
│ → introduced / carried / changed                                 │
│ → previous / next scene links                                    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ J. GENERATION CONTEXT                                           │
│                                                                 │
│ scene + canonical characters + aliases + visual facts           │
│ + objects + events + continuity + neighbors + evidence           │
│                                                                 │
│ source_grounded = true                                           │
│ unknowns_must_remain_unknown = true                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ K. GENERATION PLANNING / PROMPTING                              │
│                                                                 │
│ Generation Planner → image/video/audio plan                      │
│ → compact visual prompt compiler / Prompt Builder                │
│ → continuity + negative constraints                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ L. PROVIDER ABSTRACTION                                         │
│                                                                 │
│ Generation Job → Provider Adapter                               │
│                                                                 │
│ local SD 1.5 | Pixazo | Pollinations | OpenAI | Mock             │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ M. GENERATION QUEUE / PRODUCTION                                │
│                                                                 │
│ production_autofill → generation_queue → scheduled_at           │
│ → provider scheduler → generation job → provider                │
│ → asset registration                                             │
│                                                                 │
│ atomic queue claiming + bounded retries + stale-job recovery    │
│ + Windows scheduled runner are implemented.                      │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ N. ASSET / SOCIAL DELIVERY                                      │
│                                                                 │
│ generated master → asset registry → validation/approval          │
│ → social export                                                  │
│                                                                 │
│ Instagram Feed: 1080×1350 (4:5)                                 │
│ Instagram Reels: 1080×1920 (9:16)                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│ O. SOCIAL PUBLISHING — FUTURE                                   │
│                                                                 │
│ approved asset → Instagram / Facebook / YouTube publishing       │
└─────────────────────────────────────────────────────────────────┘
```

---

# 2. Implemented Capabilities

## A. PDF / Document Engine — DONE

- PDF inspection
- Native PDF text extraction
- OCR fallback
- Mixed PDF/text/OCR handling
- PaddleOCR integration
- Page processing
- Layout-aware text fragments
- Deterministic content normalization
- Paragraph reconstruction
- Hyphenation repair
- Raw text retention
- Text-quality metadata

## B. Structure Engine — DONE

- Generic heading detection
- Layout-aware heading detection
- Page structure classification
- Section validation
- Roman numeral OCR normalization
- Section reconciliation
- Targeted section recovery
- False-positive suppression
- Contents-page protection
- StructureScanner as the central structural path

Validated OCR examples include:

- `VIL → VII`
- `VIIL → VIII`
- `XXVIL → XXVII`
- `XXXVL → XXXVI`
- `XXXVIIL → XXXVIII`
- `DID → rejected`

## C. Canonical SQLite Document Store — DONE

SQLite is the canonical downstream structured representation.

Core document tables include:

- `documents`
- `pages`
- `sections`
- `chunks`
- `stories`
- `scenes`
- `entities`
- `entity_mentions`
- `entity_aliases`
- `events`
- `rag_documents`
- `rag_fts`

Generation/visual layers add additional tables for canonical characters, visual profiles/facts, continuity, generation jobs/queue, provider usage, and generated assets.

Supported downstream outputs include SQLite, CSV, and JSON.

## D. Story / Scene Layer — DONE

Current logical flow:

```text
Section → Story → Scenes
```

Scenes are source-grounded generation units and retain source/page relationships rather than being invented narratives.

## E. Entity Discovery / Resolution — DONE

Supports discovery and resolution of:

- characters
- locations
- environments
- events
- entity mentions
- aliases
- source evidence
- confidence

## F. Character Identity — DONE

Implemented modules include candidate gating, identity normalization, mention identity resolution, canonicalization, and identity evidence/classification.

The architecture is deliberately conservative and prevents unsafe identity merges.

## G. RAG — DONE

SQLite FTS5/BM25 retrieval is implemented over the canonical structured data.

Indexed material includes sections, stories, scenes, pages, chunks, entities, and events.

This is the current dependency-light retrieval baseline. A future embedding/vector layer is optional and should only be added for a demonstrated need.

## H. Visual Knowledge Bible — DONE

Implemented capabilities:

- canonical character visual profiles
- location/environment profiles
- visual facts
- appearance/clothing/expression/mannerism evidence
- recurring props/objects
- scene visual context
- evidence/provenance/page/scene/confidence tracking
- visual fact reconciliation
- conflict classification
- visual-bible audit
- source-grounding protection

Important rule:

> Generated guidance is not evidence. Only source-supported facts may become canonical visual facts.

The visual layer is scoped to canonical character identities; earlier raw-entity contamination was addressed in later Git commits and must not be reimplemented.

## I. Visual Continuity — DONE

Tracks:

- character presence per scene
- appearance
- clothing
- physical condition
- emotional state buckets
- scene-to-scene changes
- previous/next scene links
- persistent object mentions
- environment state
- introduced/carried/changed status

Canonical identity is not overwritten by scene-specific changes.

## J. Scene Visual State — DONE

`scene_visual_state.py` resolves which canonical characters are actually present in a scene and combines applicable visual facts into scene-effective state.

Presence does not require a visual fact. Unknown appearance therefore remains unknown.

## K. Generation Context — DONE

`generation_context.py` is the bridge from canonical knowledge to generation.

It combines:

- scene
- canonical characters
- aliases
- visual facts
- objects
- events
- continuity
- neighboring scenes
- source evidence
- generation constraints

Contract:

```text
source_grounded = true
unknowns_must_remain_unknown = true
```

## L. Generation Planner / Prompting — DONE

`generation_planner.py` produces deterministic plans containing:

- scene
- characters
- visual facts
- objects
- events
- continuity
- neighbors
- visual constraints
- source evidence
- image prompt
- video prompt
- audio prompt

`generation_prompt.py` provides the compact visual-scene compiler used for image generation.

`prompt_builder.py` provides explicit image/video prompts with negative and continuity constraints.

Do not create another prompt-building layer without first checking these two existing components.

## M. Provider Abstraction — DONE

Provider-independent generation job contract is implemented.

Current adapters include:

- `local`
- `pixazo`
- `pollinations`
- `openai`
- `mock`

Provider configuration/routing is environment/config driven.

Important current distinction:

- Local Stable Diffusion is implemented and manually selectable.
- Current automatic routing configuration should not be assumed to include `local`; inspect `config/generation_providers.json` before changing routing.

## N. Local Stable Diffusion — DONE / TESTED

Current tested local path:

- Stable Diffusion 1.5
- NVIDIA CUDA
- FP32 for stability on the Quadro T2000
- attention slicing
- CPU offload
- portrait-oriented 512×640 master generation
- output validation against obvious all-black/all-white failures
- photorealistic/cinematic prompt constraints
- negative prompt against illustration/painting styles

The local T2000 path has successfully produced generated images and social exports.

## O. Remote Provider Adapters — DONE

Pixazo adapter supports configured image/video/audio contracts.

Pollinations currently supports image generation.

OpenAI currently supports image generation.

Mock provider exists for provider-independent testing.

Do not rebuild provider adapters that already satisfy the current job contract.

## P. Generation Queue / Production — DONE

Implemented:

- generation queue
- provider-aware scheduling
- explicit provider routing order
- provider usage/quota-aware scheduling
- atomic queue claiming
- bounded provider retries
- batch scheduler
- production autofill
- stale-job watchdog/recovery
- generation status reporting
- Windows scheduled runner
- Windows Task Scheduler installer

## Q. Windows 15-Minute Scheduler — CODE DONE / MACHINE DISABLED

Repository contains the scheduled-task installer and runner.

The installer supports an `EveryMinutes` parameter and defaults to 15 minutes.

The runner performs:

```text
find document id
→ production_autofill
→ run due generation batch
```

Current machine observation:

```text
SocialAutomation-Generation    Disabled
```

Therefore:

```text
Scheduler code exists: YES
Windows task exists: YES
Windows task currently active: NO
```

This must not be confused with the scheduler implementation being absent.

## R. Asset Lifecycle — DONE

Implemented:

- generated asset registration
- provider asset identifiers
- local asset URI tracking
- validation status
- metadata
- reviewer/reason tracking
- validated/approved/rejected/review lifecycle
- asset inspection

## S. Social Export — DONE

Implemented profile-driven image export.

Current profiles:

| Profile | Output | Ratio | Mode |
|---|---:|---:|---|
| Instagram Feed | 1080×1350 | 4:5 | resize |
| Instagram Reels | 1080×1920 | 9:16 | center crop |

Generated masters are transformed into platform-standard output rather than generating arbitrary phone-specific dimensions.

---

# 3. Tested Benchmark / Current Evidence

The project has been exercised incrementally after code changes. Known tested results from the current development history include:

- 60 detected sections in the benchmark document.
- 60 stories created.
- RAG index rebuilt successfully with approximately 1500 records in the benchmark run.
- Entity extraction/resolution exercised.
- Visual pipeline and generation context exercised across representative scene IDs.
- Local Stable Diffusion generation successfully produced non-black output after switching the T2000 path to FP32.
- Successful local generation job and successful Instagram Feed social export were observed.
- Provider routing, queueing, scheduler, asset registration, and export layers have been implemented and tested incrementally.

Historical milestone documents may contain earlier numbers or pending items. Current code and later tested commits supersede stale prose.

---

# 4. Current Repository Capability Map

```text
DOCUMENT UNDERSTANDING
    ├── PDF inspection                         DONE
    ├── native extraction                     DONE
    ├── OCR                                   DONE
    ├── normalization                          DONE
    ├── structure detection                    DONE
    ├── validation/reconciliation              DONE
    └── recovery                               DONE

KNOWLEDGE
    ├── SQLite canonical store                 DONE
    ├── stories/scenes                         DONE
    ├── entities                               DONE
    ├── character identity                     DONE
    ├── events                                 DONE
    └── RAG FTS5/BM25                         DONE

VISUAL KNOWLEDGE
    ├── visual bible                           DONE
    ├── canonical visual facts                DONE
    ├── reconciliation                        DONE
    ├── conflict classification               DONE
    ├── objects/props                         DONE
    ├── scene visual context                  DONE
    └── continuity                            DONE

GENERATION
    ├── generation context                    DONE
    ├── generation planner                    DONE
    ├── prompt compiler                       DONE
    ├── prompt builder                        DONE
    ├── provider abstraction                 DONE
    ├── local SD 1.5                         DONE
    ├── Pixazo                               DONE
    ├── Pollinations                         DONE
    ├── OpenAI                               DONE
    └── mock provider                         DONE

PRODUCTION
    ├── generation queue                      DONE
    ├── autofill                              DONE
    ├── batch scheduler                       DONE
    ├── provider routing                      DONE
    ├── retries                               DONE
    ├── atomic queue lock                     DONE
    ├── watchdog                              DONE
    ├── status reporting                      DONE
    └── Windows scheduled runner              DONE

DELIVERY
    ├── asset registry                        DONE
    ├── asset validation                      DONE
    ├── Instagram Feed export                 DONE
    ├── Instagram Reels export                DONE
    ├── Facebook publishing                   NOT BUILT
    ├── Instagram publishing                  NOT BUILT
    └── YouTube publishing                    NOT BUILT

ORCHESTRATION
    └── one-command new-PDF → publish flow    NOT YET CONSOLIDATED
```

---

# 5. What We Should NOT Rebuild

Unless a regression is demonstrated, do not restart or redesign these areas:

1. PDF OCR/extraction
2. content normalization
3. StructureScanner / section detection
4. section validation/recovery
5. SQLite canonical store
6. story/scene segmentation
7. entity discovery/resolution
8. character canonicalization
9. FTS5/BM25 RAG baseline
10. visual knowledge bible
11. canonical visual fact handling
12. visual reconciliation/conflict classification
13. visual continuity
14. scene visual state
15. generation context
16. generation planner
17. prompt compiler / prompt builder
18. provider abstraction
19. local SD provider
20. remote provider adapters
21. generation queue
22. provider scheduler
23. production autofill
24. Windows scheduler implementation
25. asset lifecycle
26. social export

Any proposed change should first identify the existing module and the specific missing behavior/regression.

---

# 6. Known Gaps / Future Work

## Priority 1 — Visual generation quality / continuity

The architecture for visual continuity exists. The current quality challenge is to make generated characters and environments reliably recognizable across scenes.

Likely future work should improve the existing visual-context → prompt → provider path rather than replacing it.

## Priority 2 — Generic visual prompt compiler

`generation_prompt.py` currently contains some benchmark-book-specific extraction rules. The architecture is source-grounded, but the compact image prompt compiler should eventually become truly generic across arbitrary books.

This is a targeted improvement, not a reason to rebuild generation planning or provider infrastructure.

## Priority 3 — Local provider participation in automatic routing

The local SD provider works, but automatic provider routing must be inspected/configured explicitly if unattended Windows generation is intended to use the T2000.

Do not assume that the presence of `local_provider.py` means the scheduler currently selects it.

## Priority 4 — Consolidated new-PDF production orchestration

The individual pipeline stages exist, but a clean top-level production workflow should eventually make:

```text
new PDF
→ document pipeline
→ visual pipeline
→ generation queue
→ scheduled generation
→ assets
→ social exports
```

simple and repeatable.

This should orchestrate existing components rather than duplicate them.

## Priority 5 — Social publishing

Future platform adapters are needed for:

- Instagram
- Facebook
- YouTube

Publishing should consume approved/validated assets rather than directly publishing raw generation outputs.

## Optional future work

- richer generic visual extraction
- temporal visual state improvements
- canonical retrieval/export APIs
- embedding/vector retrieval if FTS5 proves insufficient
- video generation execution beyond current provider contracts
- audio generation execution beyond current provider contracts
- publishing analytics
- multi-book orchestration
- dashboard/UI

---

# 7. Operating Rules for Future Sessions

### Rule 1 — Read this file first

Before starting a new exercise, inspect this status document and the relevant current Git code.

### Rule 2 — Git `main` is the baseline

Assume committed code is working because the project has been tested incrementally. If something appears missing, verify the current tree before implementing anything.

### Rule 3 — Do not trust stale documentation over code

Older files such as `USER_GUIDE.txt` may describe an earlier milestone. They must not be treated as the current architecture when code/configuration has moved ahead.

### Rule 4 — Do not duplicate capabilities

Before adding a module, identify whether an existing module already owns the responsibility.

### Rule 5 — Preserve source grounding

Never convert an unknown source attribute into an invented canonical fact.

### Rule 6 — Preserve canonical identity

Do not merge characters merely because names look similar. Use the existing identity/evidence machinery.

### Rule 7 — Keep canonical facts separate from scene state

A temporary scene change must not overwrite persistent character identity facts.

### Rule 8 — Keep generation provider-independent

Provider-specific code belongs behind the provider adapter contract.

### Rule 9 — Validate after meaningful changes

Any code change should be tested before being considered complete and should be committed to Git when accepted as the new working baseline.

### Rule 10 — Update this status document daily

At the end of each meaningful work session, update:

- current milestone
- completed work
- tests run/results
- current blockers
- next exercise
- relevant commit SHA
- environment state when relevant

The goal is that both the human and the assistant can open this file at the beginning of the next session and immediately know where the project stands.

---

# 8. Daily Status Log

## 2026-09-01

### Completed / confirmed

- Reviewed current Git architecture and reconciled it against the older project documentation.
- Confirmed document engine, knowledge/RAG, visual knowledge, continuity, generation, provider, queue, scheduler, asset, and social export capabilities already exist.
- Confirmed the Windows Task Scheduler implementation exists in Git.
- Confirmed the Windows task `SocialAutomation-Generation` currently exists but is Disabled on the development machine.
- Confirmed current local Stable Diffusion path is a tested capability, not a future build item.
- Confirmed social export is already integrated into generation jobs.

### Current focus

Establish the correct end-to-end production architecture and proceed from the existing working baseline without rebuilding completed layers.

### Immediate next exercise

Work on the existing visual generation/continuity path and/or the production orchestration gaps, selecting the next task only after checking the current code and this status report.

### Relevant current baseline

Latest known development commits include the recent cinematic realism/negative-prompt changes and prior scheduler, provider, visual continuity, asset, and social-export milestones.

### Environment note

Windows Task Scheduler task:

```text
SocialAutomation-Generation    Disabled
```

Do not interpret this as scheduler code being absent.

---

# 9. Decision Log

- **SQLite** is the canonical structured downstream representation.
- **FTS5/BM25** is the current dependency-light RAG baseline.
- **Scenes** are the downstream generation unit.
- **Canonical character identity** is separate from scene-specific visual state.
- **Visual facts require source evidence.**
- **Unknown visual attributes remain unknown.**
- **Generation guidance is not evidence.**
- **Provider abstraction** separates generation orchestration from concrete providers.
- **Social export** is separate from generation resolution and uses platform-standard profiles.
- **Approved/validated assets** are the boundary before future social publishing.
- **Existing tested capabilities must not be rebuilt without a concrete reason.**

---

# 10. Next-Session Checklist

```text
[ ] Read PROJECT_STATUS.md
[ ] Check current git status / current main baseline
[ ] Identify the exact next exercise
[ ] Inspect existing implementation before writing new code
[ ] Change only the relevant layer
[ ] Run the relevant tests/regression
[ ] Confirm behavior works
[ ] Commit the working change
[ ] Update PROJECT_STATUS.md
```

---

**This document is intentionally maintained as a living project status report, not as a historical milestone document.**
