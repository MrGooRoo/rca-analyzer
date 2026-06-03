"""
Сборка FastAPI-приложения.

Использование:
    uvicorn src.api.app:app --reload
Переменные среды подгружаются из .env автоматически.
"""

from __future__ import annotations

import logging

# Загрузить .env до любых importов, которые читают os.environ
from dotenv import load_dotenv
load_dotenv()  # ищет .env в текущей папке и выше

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(MethodologyNotSupportedError)
async def methodology_error_handler(request: Request, exc: MethodologyNotSupportedError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(LLMResponseValidationError)
async def llm_error_handler(request: Request, exc: LLMResponseValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"detail": "LLM вернул невалидный ответ. Попробуйте позже."),
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": "Внутренняя ошибка сервера."})


app.include_router(analyze_router)


@app.get("/health", tags=["infra"])
async def health() -> dict:
    return {"status": "ok"}
