"""FastAPI application entry point for GridWise."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.llm.client import llm_client
from app.api.health import router as health_router
from app.api.routes import router as optimize_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("gridwise")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle management for connection pools and resources."""
    logger.info("Starting GridWise API service...")
    yield
    logger.info("Shutting down GridWise API service...")
    await llm_client.close()


app = FastAPI(
    title="GridWise — Smart Campus Energy Optimization API",
    description="LLM-assisted operator directive interpretation and deterministic mathematical energy scheduling for BUP CSE Fest 2026.",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers matching canonical endpoints
app.include_router(health_router)
app.include_router(optimize_router)

# Mount responsive web frontend
from pathlib import Path
from fastapi.staticfiles import StaticFiles

static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handles malformed or structurally invalid request payloads with a clean 400 error."""
    errors = exc.errors()
    clean_errors = [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in errors
    ]
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Request validation failed", "errors": clean_errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catches unhandled errors and returns a controlled HTTP 500 without exposing secrets or traces."""
    logger.error(f"Unhandled server error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please verify scenario parameters."},
    )
