"""FastAPI application entry point."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # noqa: E402 - must load env vars before other imports

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from src.api.middleware.csrf import CSRFMiddleware  # noqa: E402
from src.api.routes.admin import router as admin_router  # noqa: E402
from src.api.routes.analyze import router as analyze_router  # noqa: E402
from src.api.routes.export import router as export_router  # noqa: E402
from src.api.routes.upload import router as upload_router  # noqa: E402
from src.auth.router import router as auth_router  # noqa: E402
from src.auth.seed import ensure_admin_exists  # noqa: E402
from src.db.base import AsyncSessionLocal  # noqa: E402
from src.domain.models import LLMResponseValidationError, MethodologyNotSupportedError  # noqa: E402

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
    # --- Startup: fail-fast на дефолтные секреты в production ---
    jwt_secret = os.environ.get("JWT_SECRET", "")
    if not jwt_secret or "change-me" in jwt_secret.lower():
        if os.environ.get("RCA_ENV", "").lower() in ("production", "prod"):
            raise RuntimeError(
                "FAIL-FAST: JWT_SECRET не должен быть дефолтным ('change-me...') в production. "
                "Установите длинный случайный секрет через переменную окружения JWT_SECRET."
            )
        logger.warning(
            "[SECURITY] JWT_SECRET содержит значение по умолчанию ('change-me...'). "
            "Установите длинный случайный секрет через переменную окружения JWT_SECRET."
        )

    cookie_secure = os.environ.get("AUTH_COOKIE_SECURE", "false")
    if cookie_secure.lower() not in ("true", "1", "yes"):
        if os.environ.get("RCA_ENV", "").lower() in ("production", "prod"):
            raise RuntimeError(
                "FAIL-FAST: AUTH_COOKIE_SECURE должен быть 'true' в production. "
                "Установите AUTH_COOKIE_SECURE=true при работе по HTTPS."
            )
        logger.warning(
            "[SECURITY] AUTH_COOKIE_SECURE=%s — cookie будут передаваться по HTTP. "
            "В production установите AUTH_COOKIE_SECURE=true.",
            cookie_secure,
        )

    # --- Startup: seed admin из ADMIN_EMAIL ---
    try:
        async with AsyncSessionLocal() as session:
            await ensure_admin_exists(session)
    except Exception:
        logger.warning("[SEED] Не удалось выполнить admin-seed (БД недоступна?)", exc_info=True)

    # --- Startup: прогрев HF-модели эмбеддингов ---
    embeddings_provider = os.environ.get("EMBEDDINGS_PROVIDER", "local")
    if embeddings_provider in ("huggingface", "hf"):
        try:
            from src.services.embedding_service import get_embedding_service  # noqa: E402
            svc = get_embedding_service()
            import asyncio  # noqa: E402
            result = svc.embed("прогрев модели")
            if asyncio.iscoroutine(result):
                await result
            logger.info(
                "[EMBEDDINGS] HF-модель %s загружена и готова (dimension=%d)",
                svc.model_name, svc.dimension,
            )
        except Exception:
            logger.warning(
                "[EMBEDDINGS] Не удалось прогреть HF-модель; "
                "будет использован fallback на local при первом запросе.",
                exc_info=True,
            )

    yield
    # --- Shutdown ---
    try:
        from src.integrations.llm.openrouter import OpenRouterClient  # noqa: E402
        await OpenRouterClient.close_shared()
    except Exception:
        logger.warning("[SHUTDOWN] Не удалось закрыть общий OpenRouterClient", exc_info=True)


app = FastAPI(
    title="RCA Analyzer API",
    version="0.4.0",
    description="Root cause analysis for industrial incidents.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CSRF добавляется ПЕРВЫМ (внутренний слой), CORS — ПОСЛЕДНИМ (внешний слой).
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
app.include_router(upload_router)
app.include_router(admin_router)


@app.get("/health", tags=["infra"])
async def health() -> dict:
    return {"status": "ok"}
