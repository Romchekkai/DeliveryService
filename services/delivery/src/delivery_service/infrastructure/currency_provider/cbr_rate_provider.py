from decimal import Decimal

import httpx
import structlog
from delivery_service.application.interfaces.currency_rate_provider import CurrencyRateProvider
from delivery_service.domain.exceptions import CurrencyRateUnavailableError
from delivery_service.infrastructure.metrics import fx_rate_requests_total, usd_rate_rub
from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class CbrCurrencyRateProvider(CurrencyRateProvider):
    def __init__(
        self,
        redis: Redis,
        url: str,
        cache_key: str,
        cache_ttl_seconds: int,
        timeout_seconds: int = 10,
    ) -> None:
        self._redis = redis
        self._url = url
        self._cache_key = cache_key
        self._cache_ttl = cache_ttl_seconds
        self._timeout = timeout_seconds

    async def get_usd_rate(self) -> Decimal:
        cached = await self._get_cached()
        if cached is not None:
            fx_rate_requests_total.labels(source="cache").inc()
            return cached

        rate = await self._fetch_from_cbr()
        await self._cache(rate)

        fx_rate_requests_total.labels(source="cbr").inc()
        usd_rate_rub.set(float(rate))
        logger.info("fx_rate_fetched", rate=str(rate), source="cbr")
        return rate

    async def _get_cached(self) -> Decimal | None:
        try:
            value = await self._redis.get(self._cache_key)
        except Exception as e:
            logger.warning("fx_rate_cache_read_failed", error=str(e))
            return None

        if value is None:
            return None

        try:
            return Decimal(value.decode() if isinstance(value, bytes) else str(value))
        except Exception:
            return None

    async def _cache(self, rate: Decimal) -> None:
        try:
            await self._redis.set(self._cache_key, str(rate), ex=self._cache_ttl)
        except Exception as e:
            logger.warning("fx_rate_cache_write_failed", error=str(e))

    async def _fetch_from_cbr(self) -> Decimal:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(self._url)
                response.raise_for_status()
                data = response.json()
            return Decimal(str(data["Valute"]["USD"]["Value"]))
        except Exception as e:
            logger.error("fx_rate_fetch_failed", error=str(e), url=self._url)
            raise CurrencyRateUnavailableError(f"Failed to fetch rate cbr: {e}") from e
