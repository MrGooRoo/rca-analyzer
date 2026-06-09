@echo off
chcp 65001 >nul
title RCA Analyzer

echo ================================
echo  RCA Analyzer — запуск сервисов
echo ================================

REM --- Переходим в корень проекта (папка bat-файла) ---
cd /d "%~dp0"

echo.
echo [1/4] git pull...
git pull origin main

echo.
echo [2/4] Запуск бэкенда (Docker)...
docker-compose up -d

echo.
echo [3/4] Применение миграций...
docker-compose exec api alembic upgrade head

echo.
echo [4/4] Запуск фронтенда (Vite)...
start "Frontend - RCA Analyzer" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ================================
echo  Бэкенд:  http://localhost:8000
echo  Swagger: http://localhost:8000/docs
echo  Фронт:   http://localhost:5173
echo ================================
echo.
echo Это окно можно закрыть.
pause
