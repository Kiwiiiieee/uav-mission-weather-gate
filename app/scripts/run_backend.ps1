$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Local Python environment not found at $Python. Install requirements first."
}

Set-Location $Root
& $Python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
