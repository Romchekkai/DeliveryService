from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import Optional
from uuid import UUID

from delivery_service.application.interfaces.currency_rate_provider import CurrencyRateProvider
from delivery_service.domain.entities.parcel import Parcel, ParcelType
from delivery_service.domain.exceptions import CurrencyRateUnavailableError
from delivery_service.domain.repositories.parcel_repository import ParcelRepository
from delivery_service.domain.repositories.parcel_type_repository import ParcelTypeRepository
from delivery_service.domain.value_objects.parcel_status import ParcelStatus


class InMemoryParcelRepository(ParcelRepository):
    """Behaves like the SQL repository: it hands out *copies* and persists only on save."""

    def __init__(self, parcels: list[Parcel] | None = None, max_get_active_calls: int = 1_000):
        self.parcels: dict[UUID, Parcel] = {p.id: p for p in parcels or []}
        self.get_active_calls = 0
        self.saved_batches: list[list[UUID]] = []
        self.list_calls: list[tuple[UUID, int, str]] = []
        self._max_calls = max_get_active_calls

    async def get_parcel_by_id(self, parcel_id: UUID) -> Optional[Parcel]:
        parcel = self.parcels.get(parcel_id)
        return dataclasses.replace(parcel) if parcel else None

    async def get_parcels_by_user_id(
        self, user_id: UUID, paginate_rate: int = 5, p_filter: str = ""
    ) -> list[Parcel]:
        self.list_calls.append((user_id, paginate_rate, p_filter))
        found = [
            p
            for p in self.parcels.values()
            if p.user_id == user_id and p_filter.lower() in p.name.lower()
        ]
        return [dataclasses.replace(p) for p in found[:paginate_rate]]

    async def save_parcel(self, parcel: Parcel) -> None:
        self.parcels[parcel.id] = dataclasses.replace(parcel)

    async def get_active_parcels(
        self, limit: int = 500, after_id: Optional[UUID] = None
    ) -> list[Parcel]:
        self.get_active_calls += 1
        assert self.get_active_calls <= self._max_calls, (
            "get_active_parcels was called too many times - the batch loop does not terminate"
        )
        active = sorted(
            (
                p
                for p in self.parcels.values()
                if p.status == ParcelStatus.ACTIVE and (after_id is None or p.id > after_id)
            ),
            key=lambda p: p.id,
        )
        return [dataclasses.replace(p) for p in active[:limit]]

    async def save_parcels(self, parcels: list[Parcel]) -> None:
        self.saved_batches.append([p.id for p in parcels])
        for parcel in parcels:
            self.parcels[parcel.id] = dataclasses.replace(parcel)


class InMemoryParcelTypeRepository(ParcelTypeRepository):
    def __init__(self, types: list[ParcelType]):
        self.types = {t.id: t for t in types}

    async def get_parcel_types(self) -> list[ParcelType]:
        return list(self.types.values())

    async def get_parcel_by_id(self, parcel_type_id: int) -> Optional[ParcelType]:
        return self.types.get(parcel_type_id)


class FakeRateProvider(CurrencyRateProvider):
    def __init__(self, rate: str | Decimal = "90", fail: bool = False) -> None:
        self.rate = Decimal(rate)
        self.fail = fail
        self.calls = 0

    async def get_usd_rate(self) -> Decimal:
        self.calls += 1
        if self.fail:
            raise CurrencyRateUnavailableError("CBR is down")
        return self.rate


class FakeRedis:
    """Just enough of ``redis.asyncio.Redis`` for the rate provider."""

    def __init__(self, fail: bool = False) -> None:
        self.data: dict[str, bytes] = {}
        self.ttls: dict[str, int | None] = {}
        self.fail = fail

    async def get(self, key: str) -> bytes | None:
        if self.fail:
            raise ConnectionError("redis is down")
        return self.data.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        if self.fail:
            raise ConnectionError("redis is down")
        self.data[key] = value.encode()
        self.ttls[key] = ex
