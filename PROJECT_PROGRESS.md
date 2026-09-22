# Project Progress — Production Media Generation Intelligence

## Current checkpoint — 2026-09-21

The project is currently in the **real-data upstream identity validation** phase for the Asura production book.

### Current source

- PDF: `M:\\social-automation\\data\\Asura\\Asura - Tale Of The Vanquished.pdf`
- 442 pages
- 63 sections
- 191 scenes
- Branch: `llm-local-qwen`

### Verified locally

- Full test suite: **151 passed**
- Compile check: **passed**
- Focused character/identity/generation suite: **56 passed**

### Current production run

The real source pipeline has been started:

```powershell
.\\.venv\\Scripts\\python.exe -m core.pipeline "data\\Asura\\Asura - Tale Of The Vanquished.pdf"
```

It successfully recognized the PDF and entered the book-processing pipeline. Completion has not yet been reported at this checkpoint.

### Current fix under validation

The entity extractor previously suppressed a character candidate when the same name was also discovered by location/environment heuristics. This caused bare `Ravana` to be stored as a location in the production DB, while `Ravana Tomorrow` was discovered as a character.

The local fix removes that premature suppression and relies on the downstream candidate gate to resolve conflicting evidence.

### DOD status

**DOD is intentionally not running yet.**

Do not start the expensive 191-scene DOD until the regenerated DB passes the real-data Scene 1 gate:

- `King Ravana` canonical focus
- canonical ID 30
- safe alias `Ravana`
- primary moment `Tomorrow is my funeral.`
- correct source-local physical presence semantics
- canonical identity lock in the final image prompt
- no planner/runtime exception

### Resume point

Tomorrow, continue from the result of the currently running source pipeline. The next task is targeted real-data validation, then Scene 1 generation-plan smoke test, then DOD only if those gates pass.
