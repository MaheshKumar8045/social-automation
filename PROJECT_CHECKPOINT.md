## Social Automation Project Checkpoint — 2026-09-11

### Current milestone: Local LLM Successor Branch

The original `main` branch remains unchanged by this LLM milestone. All new LLM work is isolated on branch `llm-local-qwen` so it can later be pushed into a separately named successor repository.

### Baseline status before LLM work
- Original repository: `MaheshKumar8045/social-automation`
- Original branch: `main`
- Full local pytest baseline after cinematic fixes: **63 passed**
- Focused cinematic-generation suite: **8 passed**
- Real Asura DOD was being run locally for Scene 2 review.

### LLM direction agreed
Use a local LLM for semantic interpretation while retaining deterministic extraction, source-evidence validation, identity/continuity controls, and deterministic prompt QA.

Target architecture:
```text
PDF / Book
  -> Docling
  -> SQLite canonical source
  -> sections / stories / scenes / entities / continuity
  -> local Qwen scene semantic analysis
  -> exact source-evidence validation
  -> deterministic visual policy + continuity
  -> cinematic/media prompt composition
  -> deterministic prompt QA
  -> image / short video / long video prompts
```

The LLM is never treated as the source of truth. Evidence must come from the extracted book/source. LLM interpretation is rejected when source evidence cannot be verified.

### Local LLM implementation completed on `llm-local-qwen`
Added:
- `core/llm_schemas.py`
  - Pydantic schemas for scene semantics, character visibility, dialogue, visual moments, source facts, and controlled inferences.
- `core/ollama_client.py`
  - local Ollama client wrapper
  - configurable host/model/timeout
  - model availability checks
  - structured JSON-schema output
  - temperature 0
- `core/scene_semantic_llm.py`
  - strict source-grounded scene semantic interpreter
  - visible vs referenced vs unknown character classification contract
  - dialogue contamination safeguards
  - exact source-substring evidence validation
  - rejects hallucinated source moments/facts/dialogue
- `tools/check_ollama.py`
  - local Ollama connectivity/model smoke test
- `LOCAL_LLM_SETUP.md`
  - Windows install/setup instructions
  - Ollama service/model checks
  - off/shadow/enhance modes
  - architecture and evidence rules
- `tests/test_scene_semantic_llm.py`
  - validates accepted source evidence
  - rejects hallucinated primary visual moments
  - rejects hallucinated dialogue
  - verifies exact-evidence prompt contract

### Generation pipeline integration
`core/generation_planner.py` now supports:
- `SOCIAL_AUTOMATION_LLM_MODE=off|shadow|enhance`
- `SOCIAL_AUTOMATION_LLM_MODEL` (default `qwen3:30b`)
- shadow mode: run local Qwen semantic analysis and expose validated results without changing prompts
- enhance mode: allow only source-validated LLM semantics to improve dialogue, visible-character decisions, and scene/media prompt context
- enhance mode fails closed when the LLM is unavailable or its source-evidence validation rejects the scene
- plan version advanced to 8 when LLM-aware planner code is active

`core/dod.py` now supports:
```powershell
python -m core.dod "data\Asura\Asura - Tale Of The Vanquished.pdf" --llm-mode enhance --llm-model qwen3:30b
```

### Dependency
`requirements.txt` adds:
```text
ollama==0.6.2
```
The existing dependency list is retained.

### Model choice
Default local model is `qwen3:30b`.
Current Ollama catalog lists Qwen3 variants including 8B, 14B, 30B, 32B and 235B. The Qwen3 30B Ollama build is listed as a 30.5B Q4_K_M model with an approximately 19 GB download. Smaller variants remain available for lower-memory hardware.

### Local validation performed by this session
A standalone reconstruction of the new semantic modules and their unit tests was executed locally in the development environment:
```text
3 passed in 0.13s
```
This validates the Python/Pydantic semantic contract but does **not** validate actual Ollama inference because no local Ollama service/model exists in this execution environment.

### Important repository limitation
The connected GitHub capability can create/update branches, files, commits and pull requests, but it does not expose a GitHub "create repository" operation. Therefore the successor is currently prepared on the isolated branch `llm-local-qwen` of the original repository. The original `main` is left unchanged.

After the user creates the new repository, recommended name:
```text
social-automation-local-llm
```
The branch can then be pushed as the new repository's `main`.

### Windows prerequisites for the user
Install Ollama from the official installer script:
```powershell
irm https://ollama.com/install.ps1 | iex
```
Then restart PowerShell and verify:
```powershell
ollama --version
nvidia-smi
ollama pull qwen3:30b
ollama list
Invoke-RestMethod http://localhost:11434/api/tags | ConvertTo-Json -Depth 5
```
Inside the project virtual environment:
```powershell
python -m pip install -U ollama==0.6.2
python -c "import ollama; print('ollama-python import: OK')"
```
Project-specific smoke test after pulling the branch:
```powershell
python tools\check_ollama.py --model qwen3:30b
```

### Current resume point
1. User is finishing the current deterministic Asura DOD and will provide **Scene 2** output for semantic/cinematic quality review.
2. Do not change the LLM architecture based only on assumptions until Scene 2 quality is reviewed.
3. The next technical step after Scene 2 review is to create the successor repository from `llm-local-qwen` and run the local Ollama smoke test.
4. Then run LLM `shadow` mode on a small Scene 2/representative sample before enabling `enhance` for the full 191-scene DOD.
5. Only after shadow results are acceptable should full `enhance` mode become the primary LLM generation path.
