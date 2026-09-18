from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from user_service.infrastructure.logging.setup import configure_logging
from user_service.presentation.api.routers import auth_router, keys_router

configure_logging(json_logs=True)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("user_service_started")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="User Service",
        description="User registration, authentication and management service",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url="/openapi/users.json",
        docs_url="/docs",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(keys_router, prefix="/api/v1")

    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
