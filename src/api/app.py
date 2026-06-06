"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.middleware.csrf import CSRFMiddleware
from src.api.routes.admin import router as admin_router
from src.api.routes.analyze import router as analyze_router
from src.api.routes.export import router as export_router
from src.auth.router import router as auth_router
from src.auth.seed import ensure_admin_exists
from src.db.base import AsyncSessionLocal
from src.domain.models import LLMResponseValidationError, MethodologyNotSupportedError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


def _parse_origins(raw: str | None) -> list[str]:
    if raw:
        return [origin.strip() for origin in raw.split(",") if origin.strip()]
    return [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup / shutdown."""
    # --- Startup: seed admin из ADMIN_EMAIL ---
    try:
        async with AsyncSessionLocal() as session:
            await ensure_admin_exists(session)
    except Exception:
        logger.warning("[SEED] Не удалось выполнить admin-seed (БД недоступна?)", exc_info=True)
    yield
    # --- Shutdown ---


app = FastAPI(
    title="RCA Analyzer API",
    version="0.4.0",
    description="Root cause analysis for industrial incidents.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CSRF добавляется ПЕРВЫМ (внутренний слой), CORS — ПОСЛЕДНИМ (внешний слой).
# Starlette выполняет middleware в обратном порядке регистрации, поэтому такой
# порядок гарантирует, что даже на CSRF-ответ 403 навешиваются CORS-заголовки.
app.add_middleware(CSRFMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_origins(os.environ.get("CORS_ALLOW_ORIGINS")),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(MethodologyNotSupportedError)
async def methodology_error_handler(
    request: Request,
    exc: MethodologyNotSupportedError,
) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(LLMResponseValidationError)
async def llm_error_handler(request: Request, exc: LLMResponseValidationError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": "LLM returned invalid response."})


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


app.include_router(auth_router)
app.include_router(analyze_router)
app.include_router(export_router)
app.include_router(admin_router)


@app.get("/health", tags=["infra"])
async def health() -> dict:
    return {"status": "ok"}
