# AI Teacher - Windows one-command launcher
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1

Write-Host "Installing dependencies (first run downloads models)..." -ForegroundColor Cyan
pip install --quiet -r backend/requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env - add your FREE Gemini key from https://aistudio.google.com/app/apikey" -ForegroundColor Yellow
}

Set-Location backend
Write-Host "Starting AI Teacher at http://localhost:8000" -ForegroundColor Green
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload