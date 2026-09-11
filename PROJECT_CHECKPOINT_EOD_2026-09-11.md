## Social Automation Project Checkpoint — EOD 2026-09-11

### Current milestone: Local LLM / Ollama validation

The original `main` branch remains unchanged. LLM work remains isolated on `llm-local-qwen` in `MaheshKumar8045/social-automation`, pending transfer to the planned successor repository `social-automation-local-llm`.

### Repository / Python validation completed today
- Active branch: `llm-local-qwen`
- Python virtual environment: `.venv` activated successfully
- Full test suite: **67 passed in 7.55s**
- `tests/test_scene_semantic_llm.py`: **4 passed in 0.07s**
- `tests/test_cinematic_generation.py`: **8 passed in 0.08s**
- This is the current user-verified test result.

### Ollama status
Ollama was successfully installed on Windows.
- `ollama --version` -> **0.34.0**
- `ollama list` -> no models yet before pull
- `Invoke-RestMethod http://localhost:11434/api/tags` -> Ollama local API reachable; model list initially empty

### Model installation in progress
User started:
```powershell
ollama pull qwen3:30b
```
At end of session the download was in progress:
```text
1% / 18 GB
168 MB / 18 GB
2.1 MB/s
estimated ~2h23m
```
Do not assume the model pull completed. Verify with `ollama list` tomorrow.

### Next steps tomorrow
1. Open a fresh PowerShell if needed.
2. Verify:
```powershell
ollama --version
ollama list
Invoke-RestMethod http://localhost:11434/api/tags | ConvertTo-Json -Depth 5
```
3. Confirm `qwen3:30b` is present.
4. From `M:\social-automation` with `.venv` active, run:
```powershell
python tools\check_ollama.py --model qwen3:30b
```
5. Do **not** enable `enhance` yet.
6. Run the Asura deterministic baseline / review Scene 2 output if not already captured.
7. Run LLM **shadow** mode on a representative scene and compare Qwen semantic output with the deterministic/cinematic output.
8. Only after shadow results are accepted, test `enhance` mode.

### Local LLM architecture reminder
Hybrid design remains:
```text
PDF -> Docling -> SQLite -> deterministic extraction
    -> Qwen semantic interpretation
    -> exact source-evidence validation
    -> deterministic identity/continuity/visual policy
    -> cinematic/media prompt composition
    -> deterministic QA
    -> Image / Short Video / Long Video prompts
```
The LLM is not the source of truth. Unsupported evidence, dialogue, visual moments, or facts must be rejected.

### Successor repository
Planned name: `social-automation-local-llm`.
The new GitHub repository has **not** been confirmed created yet. Do not claim it exists until the user creates it with GitHub CLI.

### Important resume point
The code branch is healthy and all 67 tests pass. Ollama is installed and the `qwen3:30b` model download is currently running. Tomorrow's first task is to verify the model download, run the Ollama smoke test, then perform a controlled shadow-mode semantic validation before any production prompt enhancement.
