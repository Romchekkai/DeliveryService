"""The 5-minute job: every run (re)calculates all ACTIVE parcels, each one exactly once."""

from decimal import Decimal

import pytest
from delivery_service.application.use_cases.calculate_delivery_cost import (
    CalculateDeliveryCostsUseCase,
)
from delivery_service.domain.exceptions import CurrencyRateUnavailableError
from delivery_service.domain.value_objects.parcel_status import ParcelStatus

from tests.factories import make_parcel
from tests.fakes.repositories import FakeRateProvider, InMemoryParcelRepository

# weight 2 kg, content $10 -> base 1.10 -> cost = 1.10 * rate
EXPECTED_AT_90 = Decimal("99.00")
EXPECTED_AT_100 = Decimal("110.00")


def use_case(
    repo: InMemoryParcelRepository, rate: FakeRateProvider, batch_limit: int = 500
) -> CalculateDeliveryCostsUseCase:
    return CalculateDeliveryCostsUseCase(repo, rate, batch_limit=batch_limit)


async def test_calculates_cost_of_active_parcels() -> None:
    parcel = make_parcel()
    repo = InMemoryParcelRepository([parcel])

    processed = await use_case(repo, FakeRateProvider("90")).execute()

    assert processed == 1
    assert repo.parcels[parcel.id].delivery_cost_rub == EXPECTED_AT_90


async def test_recalculates_on_every_run_while_parcel_is_active() -> None:
    parcel = make_parcel()
    repo = InMemoryParcelRepository([parcel])
    rate = FakeRateProvider("90")
    job = use_case(repo, rate)

    await job.execute()
    rate.rate = Decimal("100")  # the CBR rate moved during the next 5 minutes
    processed = await job.execute()

    assert processed == 1
    assert repo.parcels[parcel.id].delivery_cost_rub == EXPECTED_AT_100


async def test_already_calculated_parcels_are_included_in_the_next_run() -> None:
    fresh = make_parcel()
    old = make_parcel(delivery_cost_rub=Decimal("1.00"))
    repo = InMemoryParcelRepository([fresh, old])

    processed = await use_case(repo, FakeRateProvider("90")).execute()

    assert processed == 2
    assert repo.parcels[old.id].delivery_cost_rub == EXPECTED_AT_90
    assert repo.parcels[fresh.id].delivery_cost_rub == EXPECTED_AT_90


@pytest.mark.parametrize("status", [ParcelStatus.IN_DELIVERY, ParcelStatus.CANCELED])
async def test_parcels_that_left_the_active_state_keep_their_last_cost(
    status: ParcelStatus,
) -> None:
    """Once the status changed (e.g. the user paid) the price is frozen."""
    parcel = make_parcel()
    repo = InMemoryParcelRepository([parcel])
    rate = FakeRateProvider("90")
    job = use_case(repo, rate)
    await job.execute()

    repo.parcels[parcel.id].status = status  # paid / canceled between two runs
    rate.rate = Decimal("100")
    processed = await job.execute()

    assert processed == 0
    assert repo.parcels[parcel.id].delivery_cost_rub == EXPECTED_AT_90


async def test_mixed_statuses_only_active_are_touched() -> None:
    active = make_parcel()
    paid = make_parcel(status=ParcelStatus.IN_DELIVERY, delivery_cost_rub=Decimal("5.00"))
    canceled = make_parcel(status=ParcelStatus.CANCELED)
    repo = InMemoryParcelRepository([active, paid, canceled])

    processed = await use_case(repo, FakeRateProvider("90")).execute()

    assert processed == 1
    assert repo.parcels[active.id].delivery_cost_rub == EXPECTED_AT_90
    assert repo.parcels[paid.id].delivery_cost_rub == Decimal("5.00")
    assert repo.parcels[canceled.id].delivery_cost_rub == Decimal("0")


async def test_every_parcel_is_processed_exactly_once_across_batches() -> None:
    parcels = [make_parcel() for _ in range(7)]
    repo = InMemoryParcelRepository(parcels, max_get_active_calls=10)

    processed = await use_case(repo, FakeRateProvider("90"), batch_limit=3).execute()

    assert processed == 7
    saved_ids = [pid for batch in repo.saved_batches for pid in batch]
    assert sorted(saved_ids) == sorted(p.id for p in parcels)
    assert len(saved_ids) == len(set(saved_ids))  # no parcel is handled twice
    assert [len(b) for b in repo.saved_batches] == [3, 3, 1]
    assert all(p.delivery_cost_rub == EXPECTED_AT_90 for p in repo.parcels.values())


async def test_run_terminates_when_parcels_stay_active() -> None:
    """Regression: active parcels stay ACTIVE after the calculation, the loop must still end."""
    repo = InMemoryParcelRepository([make_parcel(), make_parcel()], max_get_active_calls=5)

    await use_case(repo, FakeRateProvider("90"), batch_limit=1).execute()

    assert repo.get_active_calls <= 5


async def test_batch_exactly_equal_to_the_limit() -> None:
    repo = InMemoryParcelRepository([make_parcel() for _ in range(4)])

    processed = await use_case(repo, FakeRateProvider("90"), batch_limit=2).execute()

    assert processed == 4
    assert [len(b) for b in repo.saved_batches] == [2, 2]


async def test_no_parcels() -> None:
    repo = InMemoryParcelRepository()

    processed = await use_case(repo, FakeRateProvider("90")).execute()

    assert processed == 0
    assert repo.saved_batches == []


async def test_rate_is_requested_once_per_run() -> None:
    rate = FakeRateProvider("90")
    repo = InMemoryParcelRepository([make_parcel() for _ in range(5)])

    await use_case(repo, rate, batch_limit=2).execute()

    assert rate.calls == 1


async def test_unavailable_rate_fails_the_run_without_touching_parcels() -> None:
    parcel = make_parcel()
    repo = InMemoryParcelRepository([parcel])

    with pytest.raises(CurrencyRateUnavailableError):
        await use_case(repo, FakeRateProvider(fail=True)).execute()

    assert repo.get_active_calls == 0
    assert repo.saved_batches == []
    assert repo.parcels[parcel.id].delivery_cost_rub == Decimal("0")
