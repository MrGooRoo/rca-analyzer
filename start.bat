@echo off
title RCA Analyzer

echo ================================
echo  RCA Analyzer - starting...
echo ================================

cd /d "%~dp0"

echo:
echo [1/4] git pull...
git pull origin main

echo:
echo [2/4] Starting backend (Docker)...
docker-compose up -d

echo:
echo [3/4] Running migrations...
docker-compose exec api alembic upgrade head

echo:
echo [4/4] Starting frontend (Vite)...
start "Frontend - RCA Analyzer" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo:
echo ================================
echo  Backend:  http://localhost:8000
echo  Swagger:  http://localhost:8000/docs
echo  Frontend: http://localhost:5173
echo ================================
echo:
pause
