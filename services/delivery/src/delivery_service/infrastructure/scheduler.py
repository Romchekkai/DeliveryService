import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

from delivery_service.application.use_cases.calculate_delivery_cost import (
    CalculateDeliveryCostsUseCase,
)
from delivery_service.infrastructure.config import fx_settings, redis_settings, scheduler_settings
from delivery_service.infrastructure.currency_provider.cbr_rate_provider import (
    CbrCurrencyRateProvider,
)
from delivery_service.infrastructure.currency_provider.redis_client import redis_client
from delivery_service.infrastructure.db.repositories.sql_alc_parcel_repository import (
    SqlAlchemyParcelRepository,
)
from delivery_service.infrastructure.db.session import async_session_factory
from delivery_service.infrastructure.metrics import (
    calculation_duration_seconds,
    calculation_runs_total,
    parcels_calculated_total,
)

logger = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler()

CALCULATE_COSTS_JOB_ID = "calculate_delivery_costs"


async def run_calculate_delivery_costs(trigger: str = "scheduler") -> int:
    """A single calculation iteration. Called by both the scheduler and the admin endpoint."""
    with calculation_duration_seconds.time():
        try:
            async with async_session_factory() as session:
                rate_provider = CbrCurrencyRateProvider(
                    redis=redis_client,
                    url=fx_settings.url,
                    cache_key=redis_settings.rate_key,
                    cache_ttl_seconds=redis_settings.rate_ttl_seconds,
                    timeout_seconds=fx_settings.timeout_seconds,
                )
                use_case = CalculateDeliveryCostsUseCase(
                    parcel_repository=SqlAlchemyParcelRepository(session),
                    currency_rate_provider=rate_provider,
                )
                processed = await use_case.execute()

            parcels_calculated_total.inc(processed)
            calculation_runs_total.labels(trigger=trigger, result="success").inc()
            return processed

        except Exception as e:
            calculation_runs_total.labels(trigger=trigger, result="error").inc()
            logger.error("delivery_cost_calculation_failed", trigger=trigger, error=str(e))
            raise


def start_scheduler() -> None:
    if not scheduler_settings.enabled:
        logger.info("scheduler_disabled")
        return

    scheduler.add_job(
        run_calculate_delivery_costs,
        trigger="interval",
        minutes=scheduler_settings.calculate_costs_interval_minutes,
        id=CALCULATE_COSTS_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,  # пропущенные запуски не копятся
    )
    scheduler.start()
    logger.info(
        "scheduler_started",
        interval_minutes=scheduler_settings.calculate_costs_interval_minutes,
    )


def shutdown_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
