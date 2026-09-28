$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "Local Python environment not found at $Python. Install requirements first."
}

Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "run_backend.ps1")) -WorkingDirectory $Root
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", (Join-Path $PSScriptRoot "run_frontend.ps1")) -WorkingDirectory $Root

Write-Host "Backend:  http://127.0.0.1:8000/docs"
Write-Host "Frontend: http://localhost:8501"
