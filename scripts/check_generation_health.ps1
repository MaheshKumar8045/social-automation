param(
    [string]$Database = "data\sample_structure.db",
    [string]$Type = "image"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment Python not found: $Python" }
Set-Location $Root
& $Python -m core.generation_status $Database 1 --type $Type
if ($LASTEXITCODE -ne 0) { throw "Generation health check failed with exit code $LASTEXITCODE" }
