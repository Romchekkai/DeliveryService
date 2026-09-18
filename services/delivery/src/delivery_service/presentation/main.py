from contextlib import asynccontextmanager
from typing import AsyncIterator

import sentry_sdk
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sentry_sdk.integrations.fastapi import FastApiIntegration

from delivery_service.infrastructure.config import app_settings
from delivery_service.infrastructure.logging_setup import configure_logging
from delivery_service.infrastructure.scheduler import shutdown_scheduler, start_scheduler
from delivery_service.presentation.api.routers import admin_router, parcel_router

configure_logging("delivery", json_logs=app_settings.json_logs)
logger = structlog.get_logger(__name__)

# Sentry подключён только к сервису посылок
if app_settings.sentry_dsn:
    sentry_sdk.init(
        dsn=app_settings.sentry_dsn,
        integrations=[FastApiIntegration()],
        environment=app_settings.environment,
        traces_sample_rate=0.1,
    )
    logger.info("sentry_initialized", environment=app_settings.environment)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    start_scheduler()
    logger.info("delivery_service_started")
    yield
    shutdown_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Delivery Service",
        description="Регистрация посылок и расчёт стоимости доставки",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # в проде ограничить
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(parcel_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")

    # /metrics для Prometheus
    Instrumentator().instrument(app).expose(app, include_in_schema=False)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
