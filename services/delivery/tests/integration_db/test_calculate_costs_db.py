"""The recalculation job end-to-end: real repositories + a fake CBR rate."""

from decimal import Decimal
from typing import Any

import pytest
from delivery_service.application.use_cases.calculate_delivery_cost import (
    CalculateDeliveryCostsUseCase,
)
from delivery_service.domain.entities.parcel import ParcelType
from delivery_service.domain.exceptions import CurrencyRateUnavailableError
from delivery_service.domain.value_objects.parcel_status import ParcelStatus
from delivery_service.infrastructure import scheduler as scheduler_module
from delivery_service.infrastructure.db.repositories.sql_alc_parcel_repository import (
    SqlAlchemyParcelRepository,
)
from prometheus_client import REGISTRY
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.factories import make_parcel
from tests.fakes.repositories import FakeRateProvider


async def cost_of(session: AsyncSession, parcel_id: Any) -> Decimal:
    session.expire_all()
    parcel = await SqlAlchemyParcelRepository(session).get_parcel_by_id(parcel_id)
    assert parcel is not None
    return parcel.delivery_cost_rub


async def test_use_case_recalculates_active_parcels_on_every_run(
    session: AsyncSession, parcel_types: list[ParcelType]
) -> None:
    repo = SqlAlchemyParcelRepository(session)
    parcel = make_parcel(parcel_type=parcel_types[0])  # 2 kg, $10 -> 1.10 * rate
    await repo.save_parcel(parcel)
    rate = FakeRateProvider("90")
    job = CalculateDeliveryCostsUseCase(repo, rate)

    assert await job.execute() == 1
    assert await cost_of(session, parcel.id) == Decimal("99.00")

    rate.rate = Decimal("100")
    assert await job.execute() == 1
    assert await cost_of(session, parcel.id) == Decimal("110.00")


async def test_use_case_stops_recalculating_after_the_status_changed(
    session: AsyncSession, parcel_types: list[ParcelType]
) -> None:
    repo = SqlAlchemyParcelRepository(session)
    parcel = make_parcel(parcel_type=parcel_types[0])
    await repo.save_parcel(parcel)
    rate = FakeRateProvider("90")
    job = CalculateDeliveryCostsUseCase(repo, rate)
    await job.execute()

    paid = await repo.get_parcel_by_id(parcel.id)
    assert paid is not None
    paid.status = ParcelStatus.IN_DELIVERY  # the user paid
    await repo.save_parcel(paid)
    rate.rate = Decimal("100")

    assert await job.execute() == 0
    assert await cost_of(session, parcel.id) == Decimal("99.00")  # frozen


async def test_use_case_handles_many_batches(
    session: AsyncSession, parcel_types: list[ParcelType]
) -> None:
    repo = SqlAlchemyParcelRepository(session)
    parcels = [make_parcel(parcel_type=parcel_types[0]) for _ in range(11)]
    for parcel in parcels:
        await repo.save_parcel(parcel)
    canceled = make_parcel(parcel_type=parcel_types[0], status=ParcelStatus.CANCELED)
    await repo.save_parcel(canceled)

    processed = await CalculateDeliveryCostsUseCase(
        repo, FakeRateProvider("90"), batch_limit=4
    ).execute()

    assert processed == 11
    for parcel in parcels:
        assert await cost_of(session, parcel.id) == Decimal("99.00")
    assert await cost_of(session, canceled.id) == Decimal("0")


class TestSchedulerJob:
    """scheduler.run_calculate_delivery_costs = what APScheduler / the admin endpoint call."""

    @pytest.fixture(autouse=True)
    def wire(
        self,
        monkeypatch: pytest.MonkeyPatch,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.rate = FakeRateProvider("90")
        monkeypatch.setattr(scheduler_module, "async_session_factory", session_factory)
        monkeypatch.setattr(scheduler_module, "CbrCurrencyRateProvider", lambda **_: self.rate)

    @staticmethod
    def metric(name: str, **labels: str) -> float:
        return REGISTRY.get_sample_value(name, labels) or 0.0

    async def test_processes_parcels_and_reports_metrics(
        self, session: AsyncSession, parcel_types: list[ParcelType]
    ) -> None:
        repo = SqlAlchemyParcelRepository(session)
        parcels = [make_parcel(parcel_type=parcel_types[0]) for _ in range(3)]
        for parcel in parcels:
            await repo.save_parcel(parcel)
        runs_before = self.metric(
            "delivery_calculation_runs_total", trigger="scheduler", result="success"
        )
        parcels_before = self.metric("delivery_parcels_calculated_total")

        processed = await scheduler_module.run_calculate_delivery_costs()

        assert processed == 3
        for parcel in parcels:
            assert await cost_of(session, parcel.id) == Decimal("99.00")
        assert (
            self.metric("delivery_calculation_runs_total", trigger="scheduler", result="success")
            == runs_before + 1
        )
        assert self.metric("delivery_parcels_calculated_total") == parcels_before + 3

    async def test_manual_trigger_label(self, parcel_types: list[ParcelType]) -> None:
        before = self.metric("delivery_calculation_runs_total", trigger="manual", result="success")

        assert await scheduler_module.run_calculate_delivery_costs(trigger="manual") == 0

        assert (
            self.metric("delivery_calculation_runs_total", trigger="manual", result="success")
            == before + 1
        )

    async def test_failure_is_counted_and_reraised(
        self, session: AsyncSession, parcel_types: list[ParcelType]
    ) -> None:
        repo = SqlAlchemyParcelRepository(session)
        parcel = make_parcel(parcel_type=parcel_types[0])
        await repo.save_parcel(parcel)
        self.rate.fail = True
        before = self.metric("delivery_calculation_runs_total", trigger="scheduler", result="error")

        with pytest.raises(CurrencyRateUnavailableError):
            await scheduler_module.run_calculate_delivery_costs()

        assert (
            self.metric("delivery_calculation_runs_total", trigger="scheduler", result="error")
            == before + 1
        )
        assert await cost_of(session, parcel.id) == Decimal("0")

    async def test_next_run_recovers_after_a_failure(
        self, session: AsyncSession, parcel_types: list[ParcelType]
    ) -> None:
        repo = SqlAlchemyParcelRepository(session)
        parcel = make_parcel(parcel_type=parcel_types[0])
        await repo.save_parcel(parcel)
        self.rate.fail = True
        with pytest.raises(CurrencyRateUnavailableError):
            await scheduler_module.run_calculate_delivery_costs()

        self.rate.fail = False  # CBR is back at the next 5-minute tick

        assert await scheduler_module.run_calculate_delivery_costs() == 1
        assert await cost_of(session, parcel.id) == Decimal("99.00")
