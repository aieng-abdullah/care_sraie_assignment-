"""FastAPI application factory for the DocIntel API."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import documents, health
from app.core.config import get_settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Validate settings and install structured logging before serving traffic."""
    settings = get_settings()
    configure_logging(settings.log_level, settings.service_name)
    yield


def create_app() -> FastAPI:
    """Build the FastAPI app with versioned routers and startup hooks.

    Raises ValidationError via get_settings() if required env vars are missing,
    so a misconfigured process fails fast at boot instead of on first request.
    """
    get_settings()
    app = FastAPI(
        title="DocIntel API",
        version="0.1.0",
        description="AI-powered document intelligence: ingest, extract, validate, search.",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(documents.router)
    return app
