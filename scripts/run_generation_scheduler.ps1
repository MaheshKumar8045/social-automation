param(
    [string]$Database = "data\sample_structure.db",
    [int]$Limit = 10,
    [int]$AutofillLimit = 25,
    [string]$MediaType = "image"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "Virtual environment Python not found: $Python"
}

# Read document id from the database rather than requiring another scheduler setting.
$DocumentId = & $Python -c "import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); r=c.execute('SELECT id FROM documents ORDER BY id LIMIT 1').fetchone(); print(r[0] if r else '')" $Database
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($DocumentId)) {
    throw "Could not determine a document id from $Database"
}

& $Python -m core.production_autofill $Database $DocumentId --type $MediaType --limit $AutofillLimit
if ($LASTEXITCODE -ne 0) {
    throw "Generation queue autofill failed with exit code $LASTEXITCODE"
}

& $Python -m core.generation_batch_scheduler run-due $Database --limit $Limit
if ($LASTEXITCODE -ne 0) {
    throw "Generation scheduler failed with exit code $LASTEXITCODE"
}
