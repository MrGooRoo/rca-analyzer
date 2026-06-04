@echo off
chcp 65001 >nul

:: ═══════════════════════════════════════════════════════
::  RCA Analyzer — остановка всех сервисов
:: ═══════════════════════════════════════════════════════

set "ROOT=C:\Users\Mr_GooRoo\rca-analyzer"

cd /d "%ROOT%"

echo.
echo ╔════════════════════════════════════════════════╗
echo ║     RCA Analyzer — остановка всех сервисов    ║
echo ╚════════════════════════════════════════════════╝
echo.

echo ▸ Остановка Docker-контейнеров...
docker-compose down
echo.
echo ▸ Контейнеры остановлены  ✓
echo.
echo Закрой окно фронтенда (RCA Analyzer — Frontend) вручную.
echo.
pause
