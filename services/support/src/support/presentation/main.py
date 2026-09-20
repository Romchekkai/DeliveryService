from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from support.config import app_settings
from support.di import build_index
from support.logging_setup import configure_logging
from support.presentation.api.routers import support_router

configure_logging("support", json_logs=app_settings.json_logs)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    build_index()  # модель эмбеддингов + индекс базы знаний один раз при старте
    logger.info("support_service_started")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Support Service",
        description="Ответы на вопросы по правилам доставки",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url="/openapi/support.json",
        docs_url="/docs",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(support_router, prefix="/api/v1")

    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
