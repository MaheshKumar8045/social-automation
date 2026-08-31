param(
    [string]$Database = "data\sample_structure.db",
    [int]$Limit = 10
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found: $Python"
}

& $Python -m core.generation_batch_scheduler run-due $Database --limit $Limit
if ($LASTEXITCODE -ne 0) {
    throw "Generation scheduler failed with exit code $LASTEXITCODE"
}
