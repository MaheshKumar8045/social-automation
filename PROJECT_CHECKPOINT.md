# Social Automation — Project Checkpoint

## Goal
Build a source-grounded book/PDF-to-visual-generation knowledge pipeline. The downstream generator must produce visually coherent scenes and frame-to-frame character/object/environment continuity, down to fine details. Unknown source information must remain unknown rather than being invented.

## Environment
- Local project: `M:\social-automation`
- Python: 3.13.15
- Windows PowerShell
- Virtual environment: `.venv`
- Git branch: `main`
- GitHub repo: `MaheshKumar8045/social-automation`
- Test PDF: `data\sample.pdf`
- Test SQLite DB: `data\sample_structure.db`
- Document ID: `1`

## Pipeline built so far
```text
PDF
  -> document structure
  -> sections/stories/scenes
  -> entities + mentions + aliases + events
  -> RAG retrieval layer
  -> visual knowledge bible
  -> visual entity validation
  -> character evidence classification
  -> conservative character candidate gate
  -> identity normalization
  -> mention-level identity evidence
  -> canonical character layer
  -> NEXT: canonical characters -> Visual Knowledge Bible integration
```

## Current source-processing results
For `data/sample.pdf`:
- PDF pages: 708
- Document type: mixed
- Final sections: 60
- Stories: 60
- Scenes: 332
- Events: 332
- Pages stored: 708
- Raw entities: 2,672
- Entity mentions: 6,088
- Aliases: 2,699
- RAG records: 1,500

## RAG
RAG = Retrieval-Augmented Generation. It lets downstream AI retrieve relevant source passages instead of repeatedly supplying the entire book. RAG documents use fields including `title`, `text`, `page_start`, `page_end`, and `metadata_json`; FTS indexes `title` and `text`.

## Visual Knowledge Bible
Current build for document 1:
- Visual profiles: 2,672
- Visual facts: 4,544
- Visual objects: 31
- Object mentions: 303
- Scene visual context: 332

The Visual Bible is intended to answer: "What do we know visually about this identity/object/scene, with evidence and confidence?" It is distinct from RAG, which retrieves source text.

## Character filtering milestones
### Visual entity validation
- validated: 49
- review: 1,625
- excluded: 998

### Character evidence classifier
A later run produced:
- validated: 52
- probable: 67
- uncertain: 130
- reference: 1,457
- non_character: 966

### Conservative character candidate gate
Current result:
- validated: 41
- probable: 381
- review: 1,249
- non_character: 1,001
- total: 2,672

The gate exists because raw entity extraction produced obvious false positives such as `English`, `Here`, `Why`, `During`, `Earth`, `Orange River`, etc.

### Identity normalization
Initial normalizer produced 395 groups / 422 members / 24 multi-member groups and exposed bad containment merges such as Africa/South Africa, Sea/Central Sea, Cape/Cape Colony, etc.

The conservative normalizer now produces:
- identity groups: 404
- members: 422
- multi-member groups: 14

Good-looking aliases include:
- Arne Saknussemm / Saknussemm
- Colonel Everest / Everest
- David Livingstone / Dr Livingstone
- Humphrey Davy / Sir Humphrey Davy
- John Murray / Sir John Murray
- Matthew Strux / Mr Strux / Mr Matthew Strux
- Michael Zorn / Mr Michael Zorn
- Mr Palander / Mr Nicholas Palander / Nicholas Palander
- Mr Emery / Mr William Emery / William Emery

Questionable cases were intentionally not blindly merged, especially:
- Edwards / Mr Milne-Edwards
- Mr Hardwigg / Professor Hardwigg / Professor Von Hardwigg
- OCR-like fragments such as Professor Hard-, Sir Hum-, Sir John Mur-

### Mention-level identity evidence
`core/mention_identity_resolver.py` uses actual entity mentions and scene evidence.
Current result:
- confirmed_alias: 7
- likely_alias: 3
- ocr_fragment: 0
- unresolved: 4

### Canonical character layer
`core/character_canonicalizer.py` creates a stable canonical-character layer without deleting raw entities.
Current result:
- confirmed: 7
- likely: 3
- singleton: 390
- excluded: 4
- total canonical character records: 400

Important: the 390 singletons are surviving candidates, not automatically source-confirmed characters. Confidence/status must remain explicit.

## Important design principles
1. **Source-grounded:** never invent visual facts not supported by the source.
2. **Unknown stays unknown.**
3. **Identity is the stable key** for visual continuity.
4. **Permanent traits and scene-specific state are separate.**
5. **Every important visual fact should preserve provenance:** source passage/page/scene and confidence.
6. **Confirmed, likely, uncertain, contradictory states must remain distinguishable.**
7. **Do not hardcode names from this sample book into generic pipeline logic.** Rules should be reusable across books.
8. **Do not connect unresolved identity groups to a canonical visual profile.**
9. **Do not let geographic/object/institution containment become character identity.**

## Git milestones
Recent commits include:
- `6c9a423` Build canonical character layer from resolved identity evidence
- `f849e6a` Add mention-evidence identity resolver
- `d338b84` Make identity normalization conservative and relationship-aware
- `522ad63` Add conservative character identity normalization
- `fc36638` Add conservative character candidate gate
- `5a27fa2` Tighten character evidence scoring against false positives
- `b72959b` Add second-pass character evidence classifier
- `5b2fa7a` Add visual entity validation and normalization layer

## Exact resume point
**NEXT TASK: Canonical Character -> Visual Knowledge Bible Integration.**

The integration should:
1. Attach canonical character IDs to visual profiles.
2. Transfer existing visual facts to canonical identities.
3. Preserve source provenance and confidence.
4. Keep confirmed / likely / singleton statuses separate.
5. Keep unresolved identities isolated.
6. Detect and preserve contradictory visual descriptions.
7. Add scene-specific visual state.
8. Provide retrieval so downstream generation can ask for everything visually known about a canonical character in a specific scene.

After that, enrich canonical characters with appearance, age/apparent age, hair, facial hair, eyes, build, stature, clothing, headwear, footwear, equipment, recurring objects, relationships, roles, and temporal/scene changes — but only where supported by source evidence.

Then apply equivalent canonicalization to objects and environments.

## Safe restart commands
```powershell
cd M:\social-automation
git pull origin main
.venv\Scripts\Activate.ps1
python -m core.character_canonicalizer data\sample_structure.db 1
```

Do not assume the database is current if the PDF has been reprocessed; rerun the relevant pipeline layers after schema/code changes.
