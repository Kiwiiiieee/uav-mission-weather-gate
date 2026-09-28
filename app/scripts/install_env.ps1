$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\akaou\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not (Test-Path $Python)) {
    throw "Bundled Python runtime not found at $Python. Use a local Python 3.11+ interpreter instead."
}

Set-Location $Root
& $Python -m venv .venv
& $Python -m pip install --target .venv\Lib\site-packages -r requirements.txt
icacls .venv /grant 'Everyone:(OI)(CI)RX' /T | Out-Null

Write-Host "Environment ready in .venv"
