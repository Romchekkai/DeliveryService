import structlog

from delivery_service.application.interfaces.currency_rate_provider import CurrencyRateProvider
from delivery_service.domain.repositories.parcel_repository import ParcelRepository

logger = structlog.get_logger(__name__)


class CalculateDeliveryCostsUseCase:
    def __init__(
        self,
        parcel_repository: ParcelRepository,
        currency_rate_provider: CurrencyRateProvider,
        batch_limit: int = 500,
    ) -> None:
        self._parcel_repo = parcel_repository
        self._currency_rate_provider = currency_rate_provider
        self._batch_limit = batch_limit

    async def execute(self) -> int:
        total_updated = 0
        rate = await self._currency_rate_provider.get_usd_rate()
        while True:
            parcels = await self._parcel_repo.get_uncalculated_parcels(limit=self._batch_limit)
            if not parcels:
                break

            for parcel in parcels:
                parcel.calculate_delivery_cost(rate)

            await self._parcel_repo.save_parcels(parcels)
            total_updated += len(parcels)

        if total_updated == 0:
            logger.info("delivery_cost_calculation_skipped", reason="no_uncalculated_parcels")
        else:
            logger.info(
                "delivery_cost_calculation_finished",
                total_parcels=total_updated,
                usd_rate=str(rate),
            )

        return total_updated
