from decimal import Decimal
from typing import Any, Callable

import httpx
import pytest
from delivery_service.domain.exceptions import CurrencyRateUnavailableError
from delivery_service.infrastructure.currency_provider import cbr_rate_provider
from delivery_service.infrastructure.currency_provider.cbr_rate_provider import (
    CbrCurrencyRateProvider,
)

from tests.fakes.repositories import FakeRedis

CBR_PAYLOAD = {"Valute": {"USD": {"Value": 84.1723}, "EUR": {"Value": 91.5}}}


class CbrStub:
    """Replaces the HTTP layer of the provider with an httpx.MockTransport."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.requests: list[httpx.Request] = []
        self.handler: Callable[[httpx.Request], httpx.Response] = lambda r: httpx.Response(
            200, json=CBR_PAYLOAD
        )
        real_client = httpx.AsyncClient

        def factory(**kwargs: Any) -> httpx.AsyncClient:
            def handler(request: httpx.Request) -> httpx.Response:
                self.requests.append(request)
                return self.handler(request)

            return real_client(transport=httpx.MockTransport(handler), **kwargs)

        monkeypatch.setattr(cbr_rate_provider.httpx, "AsyncClient", factory)


@pytest.fixture
def cbr(monkeypatch: pytest.MonkeyPatch) -> CbrStub:
    return CbrStub(monkeypatch)


def make_provider(redis: FakeRedis) -> CbrCurrencyRateProvider:
    return CbrCurrencyRateProvider(
        redis=redis,  # type: ignore[arg-type]
        url="https://cbr.test/daily_json.js",
        cache_key="fx:usd_rub",
        cache_ttl_seconds=3600,
    )


async def test_fetches_rate_from_cbr_and_caches_it(cbr: CbrStub) -> None:
    redis = FakeRedis()

    rate = await make_provider(redis).get_usd_rate()

    assert rate == Decimal("84.1723")
    assert len(cbr.requests) == 1
    assert str(cbr.requests[0].url) == "https://cbr.test/daily_json.js"
    assert redis.data["fx:usd_rub"] == b"84.1723"
    assert redis.ttls["fx:usd_rub"] == 3600


async def test_cache_hit_does_not_call_cbr(cbr: CbrStub) -> None:
    redis = FakeRedis()
    redis.data["fx:usd_rub"] = b"77.5"

    rate = await make_provider(redis).get_usd_rate()

    assert rate == Decimal("77.5")
    assert cbr.requests == []


async def test_second_call_is_served_from_cache(cbr: CbrStub) -> None:
    provider = make_provider(FakeRedis())

    first = await provider.get_usd_rate()
    second = await provider.get_usd_rate()

    assert first == second
    assert len(cbr.requests) == 1


async def test_corrupted_cache_entry_falls_back_to_cbr(cbr: CbrStub) -> None:
    redis = FakeRedis()
    redis.data["fx:usd_rub"] = b"not-a-number"

    rate = await make_provider(redis).get_usd_rate()

    assert rate == Decimal("84.1723")
    assert len(cbr.requests) == 1


async def test_redis_outage_does_not_break_the_calculation(cbr: CbrStub) -> None:
    rate = await make_provider(FakeRedis(fail=True)).get_usd_rate()

    assert rate == Decimal("84.1723")


async def test_cbr_http_error(cbr: CbrStub) -> None:
    cbr.handler = lambda r: httpx.Response(503)

    with pytest.raises(CurrencyRateUnavailableError):
        await make_provider(FakeRedis()).get_usd_rate()


async def test_cbr_unreachable(cbr: CbrStub) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    cbr.handler = refuse

    with pytest.raises(CurrencyRateUnavailableError):
        await make_provider(FakeRedis()).get_usd_rate()


@pytest.mark.parametrize(
    "payload", [{}, {"Valute": {}}, {"Valute": {"USD": {}}}, {"Valute": {"USD": {"Value": "x"}}}]
)
async def test_unexpected_payload(cbr: CbrStub, payload: dict[str, Any]) -> None:
    cbr.handler = lambda r: httpx.Response(200, json=payload)

    with pytest.raises(CurrencyRateUnavailableError):
        await make_provider(FakeRedis()).get_usd_rate()


async def test_failed_fetch_is_not_cached(cbr: CbrStub) -> None:
    cbr.handler = lambda r: httpx.Response(500)
    redis = FakeRedis()

    with pytest.raises(CurrencyRateUnavailableError):
        await make_provider(redis).get_usd_rate()

    assert redis.data == {}
