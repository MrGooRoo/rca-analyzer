"""
Сборка FastAPI-приложения.

Использование:
    uvicorn src.api.app:app --reload
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes.analyze import router as analyze_router
from src.domain.models import LLMResponseValidationError, MethodologyNotSupportedError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

app = FastAPI(
    title="RCA Analyzer API",
    version="0.1.0",
    description="Автоматический анализ корневых причин производственных инцидентов.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — разрешаем фронт на localhost при разработке
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Глобальные обработчики ошибок
# ---------------------------------------------------------------------------

@app.exception_handler(MethodologyNotSupportedError)
async def methodology_error_handler(request: Request, exc: MethodologyNotSupportedError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(LLMResponseValidationError)
async def llm_error_handler(request: Request, exc: LLMResponseValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": "LLM вернул невалидный ответ. Попробуйте позже."},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервера."})


# ---------------------------------------------------------------------------
# Роутеры
# ---------------------------------------------------------------------------

app.include_router(analyze_router)


@app.get("/health", tags=["infra"])
async def health() -> dict:
    """Healthcheck для Docker / k8s probe."""
    return {"status": "ok"}
