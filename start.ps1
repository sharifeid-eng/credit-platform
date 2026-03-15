# Laith — Start both backend and frontend servers
# Usage: .\start.ps1

Write-Host ""
Write-Host "  LAITH — Starting servers..." -ForegroundColor Yellow
Write-Host ""

# Start backend (FastAPI + uvicorn) in a new terminal
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$PSScriptRoot';
    Write-Host '  [Backend] Starting FastAPI on localhost:8000...' -ForegroundColor Cyan;
    & '$PSScriptRoot\venv\Scripts\activate.ps1';
    Set-Location backend;
    python -m uvicorn main:app --reload
"

# Start frontend (Vite) in a new terminal
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$PSScriptRoot\frontend';
    Write-Host '  [Frontend] Starting Vite on localhost:5173...' -ForegroundColor Cyan;
    npm run dev
"

Write-Host "  Backend:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Cyan
Write-Host ""

# Wait a moment then open the browser
Start-Sleep -Seconds 3
Start-Process "http://localhost:5173"
