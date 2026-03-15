# Laith — Start both backend and frontend servers
# Usage: .\start.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $root) { $root = Get-Location }

Write-Host ""
Write-Host "  LAITH Starting servers..." -ForegroundColor Yellow
Write-Host ""

$backendCmd = "Set-Location '$root'; Write-Host '  [Backend] Starting FastAPI on localhost:8000...' -ForegroundColor Cyan; & '$root\venv\Scripts\activate.ps1'; Set-Location backend; python -m uvicorn main:app --reload"

$frontendCmd = "Set-Location '$root\frontend'; Write-Host '  [Frontend] Starting Vite on localhost:5173...' -ForegroundColor Cyan; npm run dev"

Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host ""

Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
