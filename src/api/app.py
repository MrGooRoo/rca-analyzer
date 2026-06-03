"""
FastAPI application entry point.

Usage:
    uvicorn src.api.app:app --reload

Environment variables are loaded from .env automatically.
"""

from __future__ import annotations

import logging

from dotenv import load_dotenv
load_dotenv()

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
    description="Root cause analysis for industrial incidents.",
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
        content={"detail": "LLM returned invalid response. Please try again later."},
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger(__name__).exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


app.include_router(analyze_router)


@app.get("/health", tags=["infra"])
async def health() -> dict:
    return {"status": "ok"}
