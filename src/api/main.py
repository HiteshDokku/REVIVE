"""REVIVE FastAPI application entry point.

Creates and configures the FastAPI application instance with:
- Health check endpoint
- Structured error handling
- CORS middleware (development)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.config import settings
from src.api.schemas import HealthResponse

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup/shutdown events."""
    logger.info(
        "Starting %s v%s (env=%s)",
        settings.app_name,
        settings.app_version,
        settings.app_env,
    )
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    # --- Health endpoint ---
    @application.get(
        "/health",
        response_model=HealthResponse,
        tags=["system"],
        summary="Health check",
        description="Returns the current health status of the application.",
    )
    async def health() -> HealthResponse:
        """Return application health status."""
        return HealthResponse.ok(
            app_name=settings.app_name,
            version=settings.app_version,
        )

    # --- Global exception handler ---
    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch unhandled exceptions and return a structured error response.

        Never expose raw stack traces to end users (AGENTS.md §15).
        """
        logger.exception("Unhandled exception for %s %s", request.method, request.url)
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred.",
            },
        )

    return application


# Application instance used by uvicorn
app = create_app()
