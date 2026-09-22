# Local LLM Setup

This branch adds an optional local semantic-intelligence layer using Ollama and Qwen3. The original `main` behavior remains unchanged unless LLM mode is explicitly enabled.

## Recommended local model

Default model:

```text
qwen3:30b
```

Ollama currently publishes Qwen3 30B as a 30.5B-parameter Q4_K_M model with an approximately 19 GB model download. Smaller Qwen3 variants are available if local hardware cannot comfortably run 30B.

## Windows prerequisites

Install Ollama using the official installer script in PowerShell:

```powershell
irm https://ollama.com/install.ps1 | iex
```

Close and reopen PowerShell after installation, then verify:

```powershell
ollama --version
```

Check NVIDIA GPU visibility when applicable:

```powershell
nvidia-smi
```

Pull the recommended model:

```powershell
ollama pull qwen3:30b
```

Confirm it is installed:

```powershell
ollama list
```

Run a direct smoke test:

```powershell
ollama run qwen3:30b
```

Then type:

```text
Return only this JSON: {"ok":true}
```

Press Ctrl+D or Ctrl+C to exit.

## Python dependency

Inside the project virtual environment:

```powershell
python -m pip install -U ollama==0.6.2
python -c "import ollama; print('ollama-python import: OK')"
```

The repository also pins this dependency in `requirements.txt`.

## Local service smoke test

Ollama serves its local API on port 11434.

```powershell
Invoke-RestMethod http://localhost:11434/api/tags | ConvertTo-Json -Depth 5
```

The response should list `qwen3:30b` after the model has been pulled.

## Project modes

Default deterministic behavior:

```powershell
$env:SOCIAL_AUTOMATION_LLM_MODE="off"
```

Shadow mode: Qwen analyzes each scene and its output is source-validated, but it does not modify the generated prompts:

```powershell
$env:SOCIAL_AUTOMATION_LLM_MODE="shadow"
$env:SOCIAL_AUTOMATION_LLM_MODEL="qwen3:30b"
```

Enhance mode: source-validated Qwen semantics are allowed to improve scene interpretation, dialogue overlays, visible-character decisions, and media prompt context. A rejected/unavailable LLM analysis fails the scene rather than silently substituting unverified content:

```powershell
$env:SOCIAL_AUTOMATION_LLM_MODE="enhance"
$env:SOCIAL_AUTOMATION_LLM_MODEL="qwen3:30b"
```

The DOD command can also set these options directly:

```powershell
python -m core.dod "data\Asura\Asura - Tale Of The Vanquished.pdf" --llm-mode enhance --llm-model qwen3:30b
```

## Architecture

```text
PDF / Book
  -> Docling
  -> SQLite canonical source
  -> sections / stories / scenes / entities / continuity
  -> local Qwen scene semantic analysis
  -> exact source-evidence validation
  -> deterministic visual policy + continuity
  -> cinematic media compiler
  -> deterministic prompt QA
  -> image / short video / long video prompts
```

The LLM is not the source of truth. It is a semantic interpreter whose claims must survive deterministic source-evidence validation before they can influence generation.

## Structured output contract

Ollama structured outputs are requested with the project's Pydantic JSON Schema and `temperature=0`. Evidence fields must be exact source substrings. This prevents a locally generated paraphrase or hallucination from silently becoming source fact.
