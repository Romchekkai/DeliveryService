from decimal import Decimal
from uuid import uuid4

import pytest
from delivery_service.application.dto.parcel_dto import ParcelInputDTO
from delivery_service.application.use_cases.get_parcel_by_id import GetParcelsByIdUseCase
from delivery_service.application.use_cases.get_parcel_types import GetParcelTypesUseCase
from delivery_service.application.use_cases.get_parcels_by_user import GetParcelsByUserUseCase
from delivery_service.application.use_cases.parcel_create import CreateParcelUseCase
from delivery_service.domain.exceptions import (
    ParcelIncorrectWeightError,
    ParcelNotFoundError,
    ParcelTypeNotFoundError,
)
from delivery_service.domain.value_objects.parcel_status import ParcelStatus
from pydantic import ValidationError

from tests.factories import CLOTHES, ELECTRONICS, OTHER, make_parcel
from tests.fakes.repositories import InMemoryParcelRepository, InMemoryParcelTypeRepository


class TestCreateParcel:
    def make(self) -> tuple[CreateParcelUseCase, InMemoryParcelRepository]:
        repo = InMemoryParcelRepository()
        types = InMemoryParcelTypeRepository([CLOTHES, ELECTRONICS, OTHER])
        return CreateParcelUseCase(repo, types), repo

    async def test_creates_and_saves_an_active_parcel(self) -> None:
        use_case, repo = self.make()
        owner = uuid4()

        result = await use_case.execute(
            ParcelInputDTO(
                user_id=owner, name="Laptop", weight=2.5, parcel_type_id=2, content_cost_cents=99900
            )
        )

        assert result.name == "Laptop"
        assert result.parcel_type == ELECTRONICS
        stored = repo.parcels[result.id]
        assert stored.user_id == owner
        assert stored.status is ParcelStatus.ACTIVE
        assert stored.content_cost_cents == 99900

    async def test_cost_is_not_calculated_at_creation_time(self) -> None:
        use_case, repo = self.make()

        result = await use_case.execute(
            ParcelInputDTO(
                user_id=uuid4(), name="Book", weight=1, parcel_type_id=1, content_cost_cents=100
            )
        )

        assert result.delivery_cost_rub == "Не рассчитано"
        assert repo.parcels[result.id].delivery_cost_rub == Decimal("0")

    async def test_unknown_parcel_type(self) -> None:
        use_case, repo = self.make()

        with pytest.raises(ParcelTypeNotFoundError):
            await use_case.execute(
                ParcelInputDTO(
                    user_id=uuid4(), name="Book", weight=1, parcel_type_id=99, content_cost_cents=1
                )
            )
        assert repo.parcels == {}

    async def test_domain_validation_errors_are_propagated(self) -> None:
        use_case, repo = self.make()

        with pytest.raises(ParcelIncorrectWeightError):
            await use_case.execute(
                ParcelInputDTO(
                    user_id=uuid4(), name="Book", weight=0, parcel_type_id=1, content_cost_cents=1
                )
            )
        assert repo.parcels == {}

    def test_dto_rejects_wrong_types(self) -> None:
        with pytest.raises(ValidationError):
            ParcelInputDTO(
                user_id="not-a-uuid",  # type: ignore[arg-type]
                name="Book",
                weight=1,
                parcel_type_id=1,
                content_cost_cents=1,
            )


class TestGetParcelById:
    async def test_returns_own_parcel(self) -> None:
        parcel = make_parcel(name="Mine", weight_kg=3.0, content_cost_cents=250)
        use_case = GetParcelsByIdUseCase(InMemoryParcelRepository([parcel]))

        result = await use_case.execute(parcel.id, parcel.user_id)

        assert result is not None
        assert result.id == parcel.id
        assert result.name == "Mine"
        assert result.weight_kg == 3.0
        assert result.parcel_type == CLOTHES.name
        assert result.content_cost_usd == Decimal("2.50")
        assert result.delivery_cost_rub == "Не рассчитано"
        assert result.status == "active"

    async def test_calculated_cost_is_formatted(self) -> None:
        parcel = make_parcel(delivery_cost_rub=Decimal("99"))
        use_case = GetParcelsByIdUseCase(InMemoryParcelRepository([parcel]))

        result = await use_case.execute(parcel.id, parcel.user_id)

        assert result is not None and result.delivery_cost_rub == "99.00"

    async def test_foreign_parcel_looks_like_not_found(self) -> None:
        parcel = make_parcel()
        use_case = GetParcelsByIdUseCase(InMemoryParcelRepository([parcel]))

        with pytest.raises(ParcelNotFoundError):
            await use_case.execute(parcel.id, uuid4())

    async def test_unknown_parcel(self) -> None:
        use_case = GetParcelsByIdUseCase(InMemoryParcelRepository())

        with pytest.raises(ParcelNotFoundError):
            await use_case.execute(uuid4(), uuid4())


class TestGetParcelsByUser:
    async def test_maps_parcels_to_short_dtos(self) -> None:
        owner = uuid4()
        calculated = make_parcel(user_id=owner, name="A", delivery_cost_rub=Decimal("12.5"))
        pending = make_parcel(user_id=owner, name="B", parcel_type=OTHER)
        repo = InMemoryParcelRepository([calculated, pending, make_parcel()])

        result = await GetParcelsByUserUseCase(repo).execute(owner)

        assert {(p.name, p.parcel_type, p.delivery_cost_rub) for p in result} == {
            ("A", "Одежда", "12.50"),
            ("B", "Разное", "Не рассчитано"),
        }

    async def test_passes_pagination_and_filter_to_the_repository(self) -> None:
        owner = uuid4()
        repo = InMemoryParcelRepository()

        await GetParcelsByUserUseCase(repo).execute(owner, 20, "book")

        assert repo.list_calls == [(owner, 20, "book")]

    async def test_no_parcels(self) -> None:
        assert await GetParcelsByUserUseCase(InMemoryParcelRepository()).execute(uuid4()) == []


class TestGetParcelTypes:
    async def test_returns_all_types(self) -> None:
        use_case = GetParcelTypesUseCase(InMemoryParcelTypeRepository([CLOTHES, ELECTRONICS]))

        result = await use_case.execute()

        assert [(t.id, t.name) for t in result] == [(1, "Одежда"), (2, "Электроника")]

    async def test_empty(self) -> None:
        assert await GetParcelTypesUseCase(InMemoryParcelTypeRepository([])).execute() == []
