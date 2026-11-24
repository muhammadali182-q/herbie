"""HTTP API entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from herbie import __version__
from herbie.config import Settings, get_settings
from herbie.logging import configure_logging


class HealthResponse(BaseModel):
    """Stable health response contract."""

    status: str
    service: str
    version: str
    environment: str


class MetaResponse(BaseModel):
    """Public API metadata."""

    name: str
    version: str
    protocol: str
    phase: str


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an API instance with explicit settings for testability."""

    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)
    logger = structlog.get_logger("herbie.api")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info(
            "api_started",
            environment=app_settings.environment,
            version=__version__,
        )
        yield
        logger.info("api_stopped")

    application = FastAPI(
        title="H.E.R.B.I.E. Platform API",
        version=__version__,
        description="Multi-tenant EV charging management platform",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "If-Match"],
    )

    @application.get("/health/live", response_model=HealthResponse, tags=["health"])
    async def liveness() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service="api",
            version=__version__,
            environment=app_settings.environment,
        )

    @application.get("/health/ready", response_model=HealthResponse, tags=["health"])
    async def readiness() -> HealthResponse:
        # Dependency checks are added with their adapters. A static response is
        # honest while this foundation has no runtime dependency clients.
        return HealthResponse(
            status="ready",
            service="api",
            version=__version__,
            environment=app_settings.environment,
        )

    @application.get("/api/v1/meta", response_model=MetaResponse, tags=["platform"])
    async def metadata() -> MetaResponse:
        return MetaResponse(
            name="H.E.R.B.I.E.",
            version=__version__,
            protocol="simplified-mqtt-v1",
            phase="foundation",
        )

    return application


app = create_app()


def run() -> None:
    """Run the API through the package console script."""

    settings = get_settings()
    uvicorn.run(
        "herbie.main:app",
        host=settings.api_host,
        port=settings.api_port,
        log_config=None,
    )


if __name__ == "__main__":  # pragma: no cover - module execution guard
    run()
