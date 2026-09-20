import pytest
from delivery_service.domain.entities.parcel import ParcelType
from delivery_service.infrastructure.db.repositories.sql_alc_parcel_type_repository import (
    SqlAlchemyParcelTypeRepository,
)
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def repo(session: AsyncSession) -> SqlAlchemyParcelTypeRepository:
    return SqlAlchemyParcelTypeRepository(session)


async def test_get_parcel_types(
    repo: SqlAlchemyParcelTypeRepository, parcel_types: list[ParcelType]
) -> None:
    result = await repo.get_parcel_types()

    assert sorted(result, key=lambda t: t.id) == parcel_types


async def test_get_parcel_types_when_empty(repo: SqlAlchemyParcelTypeRepository) -> None:
    assert await repo.get_parcel_types() == []


async def test_get_parcel_by_id(
    repo: SqlAlchemyParcelTypeRepository, parcel_types: list[ParcelType]
) -> None:
    assert await repo.get_parcel_by_id(2) == ParcelType(2, "Электроника")


async def test_get_parcel_by_id_unknown_returns_none(
    repo: SqlAlchemyParcelTypeRepository, parcel_types: list[ParcelType]
) -> None:
    assert await repo.get_parcel_by_id(999) is None
