@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ═══════════════════════════════════════════════════════
::  RCA Analyzer — стартовый скрипт
::  Поднимает: Docker (API + БД), миграции, фронтенд
::  Версия: 1.0  |  05.06.2026
:: ═══════════════════════════════════════════════════════

set "ROOT=C:\Users\Mr_GooRoo\rca-analyzer"
set "FRONTEND=%ROOT%\frontend"

title RCA Analyzer — запуск...

echo.
echo ╔════════════════════════════════════════════════╗
echo ║     RCA Analyzer — запуск всех сервисов       ║
echo ╚════════════════════════════════════════════════╝
echo.

:: ── 1. Переход в корень проекта ──────────────────────
echo [1/5] ▸ Переход в корень проекта...
cd /d "%ROOT%"
if %errorlevel% neq 0 (
    echo [ОШИБКА] Не удалось зайти в %ROOT%
    pause
    exit /b 1
)
echo        %ROOT%  ✓
echo.

:: ── 2. Git pull ──────────────────────────────────────
echo [2/5] ▸ Обновление репозитория (git pull)...
git pull origin main
if %errorlevel% neq 0 (
    echo [ПРЕДУПРЕЖДЕНИЕ] git pull завершился с ошибкой — продолжаем
)
echo.

:: ── 3. Docker — остановить старое, запустить новое ──
echo [3/5] ▸ Остановка старых контейнеров...
docker-compose down 2>nul
echo        ▸ Запуск Docker-контейнеров (API + PostgreSQL)...
docker-compose up -d --build
if %errorlevel% neq 0 (
    echo [ОШИБКА] Docker не смог запустить контейнеры
    echo        Проверь, запущен ли Docker Desktop
    pause
    exit /b 1
)
echo        Контейнеры запущены  ✓
echo.

:: ── 4. Ожидание API + миграции ──────────────────────
echo [4/5] ▸ Ожидание API (проверка healthcheck)...
set RETRIES=0
:wait_api
timeout /t 3 /nobreak >nul
set /a RETRIES+=1
curl -s -o nul http://localhost:8000/health 2>nul
if %errorlevel% equ 0 (
    echo        API готов (попытка %RETRIES%)  ✓
    goto run_migrations
)
if %RETRIES% lss 15 goto wait_api
echo [ПРЕДУПРЕЖДЕНИЕ] API не ответил за 45 секунд — пробую миграции...

:run_migrations
echo        ▸ Применение миграций Alembic...
docker-compose exec -T api alembic upgrade head
if %errorlevel% equ 0 (
    echo        Миграции применены  ✓
) else (
    echo [ПРЕДУПРЕЖДЕНИЕ] Миграции не применились — проверь БД
)
echo.

:: ── 5. Фронтенд (в новом окне) ──────────────────────
echo [5/5] ▸ Запуск фронтенда в отдельном окне...
if not exist "%FRONTEND%\node_modules" (
    echo        ▸ Установка npm-зависимостей (первый запуск)...
    cd /d "%FRONTEND%"
    call npm install
    cd /d "%ROOT%"
)

start "RCA Analyzer — Frontend" cmd /c "cd /d "%FRONTEND%" && title RCA Analyzer — Frontend :5173 && echo. && echo  Frontend запущен на http://localhost:5173 && echo  Закрой это окно чтобы остановить фронтенд && echo. && npm run dev"

echo        Фронтенд запускается в отдельном окне  ✓
echo.

:: ── Итог ────────────────────────────────────────────
echo ╔════════════════════════════════════════════════╗
echo ║           ВСЕ СЕРВИСЫ ЗАПУЩЕНЫ               ║
echo ╠════════════════════════════════════════════════╣
echo ║  API + Swagger:  http://localhost:8000/docs   ║
echo ║  Frontend:       http://localhost:5173        ║
echo ║  PostgreSQL:     localhost:5432               ║
echo ╚════════════════════════════════════════════════╝
echo.
echo Нажми любую клавишу чтобы закрыть это окно...
pause >nul
