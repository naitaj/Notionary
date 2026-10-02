# Notionary Local Development Starter Script for Windows
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       Starting Notionary Workspace      " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. Start Backend in separate window or background
Write-Host "[1/2] Launching FastAPI Backend on http://localhost:8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Starting Notionary Backend...'; & backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --app-dir backend"

# 2. Start Frontend
Write-Host "[2/2] Launching Next.js Frontend on http://localhost:3000..." -ForegroundColor Green
Set-Location -Path "frontend"
npm run dev
