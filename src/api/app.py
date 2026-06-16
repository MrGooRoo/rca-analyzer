"""
FastAPI application factory.
"""
from __future__ import annotations

import logging
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.api.middleware.csrf import CSRFMiddleware
from src.api.routes import analyze, auth, results, sessions, embeddings
from src.db.base import engine
from src.db.models import Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    # --- Startup ---
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    embeddings_provider = os.getenv("EMBEDDINGS_PROVIDER", "local")
    if embeddings_provider in ("huggingface", "hf"):
        try:
            from src.integrations.embeddings.hf_local import HFLocalEmbeddingService
            svc = HFLocalEmbeddingService()
            await svc.warmup()
            logger.info("[STARTUP] HF embedding model warmed up successfully")
        except Exception:
            logger.warning(
                "[STARTUP] Could not warm up HF embedding model",
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
    lifespan=lifespan,
)

# CORS
origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CSRF
app.add_middleware(CSRFMiddleware)

# Routers
app.include_router(auth.router,      prefix="/api/v1")
app.include_router(analyze.router,   prefix="/api/v1")
app.include_router(results.router,   prefix="/api/v1")
app.include_router(sessions.router,  prefix="/api/v1")
app.include_router(embeddings.router, prefix="/api/v1")

# Static files (React build)
_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        index = os.path.join(_DIST, "index.html")
        return FileResponse(index)
