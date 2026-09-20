import uuid
from decimal import Decimal

import pytest
from delivery_service.domain.entities.parcel import ParcelType
from delivery_service.domain.value_objects.parcel_status import ParcelStatus
from delivery_service.infrastructure.db.repositories.sql_alc_parcel_repository import (
    SqlAlchemyParcelRepository,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import make_parcel


@pytest.fixture
def repo(session: AsyncSession) -> SqlAlchemyParcelRepository:
    return SqlAlchemyParcelRepository(session)


async def test_save_and_get_by_id(
    repo: SqlAlchemyParcelRepository, parcel_types: list[ParcelType]
) -> None:
    parcel = make_parcel(
        name="Laptop", weight_kg=232.231, content_cost_cents=455, parcel_type=parcel_types[1]
    )
    await repo.save_parcel(parcel)

    found = await repo.get_parcel_by_id(parcel.id)

    assert found is not None
    assert found.id == parcel.id
    assert found.user_id == parcel.user_id
    assert found.name == "Laptop"
    assert found.weight_kg == 232.231
    assert found.type == ParcelType(2, "Электроника")  # the joined type is loaded
    assert found.content_cost_cents == 455
    assert found.delivery_cost_rub == Decimal("0")
    assert found.status is ParcelStatus.ACTIVE


async def test_get_by_id_unknown_returns_none(repo: SqlAlchemyParcelRepository) -> None:
    assert await repo.get_parcel_by_id(uuid.uuid4()) is None


async def test_save_existing_parcel_updates_it(
    repo: SqlAlchemyParcelRepository, session: AsyncSession, parcel_types: list[ParcelType]
) -> None:
    parcel = make_parcel(parcel_type=parcel_types[0])
    await repo.save_parcel(parcel)

    parcel.calculate_delivery_cost(Decimal("90"))
    parcel.change_type(parcel_types[2])
    await repo.save_parcel(parcel)
    session.expire_all()

    found = await repo.get_parcel_by_id(parcel.id)
    assert found is not None
    assert found.delivery_cost_rub == Decimal("99.00")
    assert found.type == parcel_types[2]


async def test_unknown_parcel_type_violates_fk(
    repo: SqlAlchemyParcelRepository, parcel_types: list[ParcelType]
) -> None:
    with pytest.raises(IntegrityError):
        await repo.save_parcel(make_parcel(parcel_type=ParcelType(999, "ghost")))


async def test_user_can_have_several_parcels(
    repo: SqlAlchemyParcelRepository, parcel_types: list[ParcelType]
) -> None:
    owner = uuid.uuid4()

    await repo.save_parcel(make_parcel(user_id=owner, name="first", parcel_type=parcel_types[0]))
    await repo.save_parcel(make_parcel(user_id=owner, name="second", parcel_type=parcel_types[0]))

    assert len(await repo.get_parcels_by_user_id(owner)) == 2


class TestGetParcelsByUser:
    async def test_returns_only_the_owners_parcels(
        self, repo: SqlAlchemyParcelRepository, parcel_types: list[ParcelType]
    ) -> None:
        alice, bob = uuid.uuid4(), uuid.uuid4()
        await repo.save_parcel(make_parcel(user_id=alice, name="a1", parcel_type=parcel_types[0]))
        await repo.save_parcel(make_parcel(user_id=bob, name="b1", parcel_type=parcel_types[0]))

        result = await repo.get_parcels_by_user_id(alice)

        assert [p.name for p in result] == ["a1"]

    async def test_limit(
        self, repo: SqlAlchemyParcelRepository, parcel_types: list[ParcelType]
    ) -> None:
        owner = uuid.uuid4()
        for i in range(8):
            await repo.save_parcel(
                make_parcel(user_id=owner, name=f"p{i}", parcel_type=parcel_types[0])
            )

        assert len(await repo.get_parcels_by_user_id(owner)) == 5  # default page size
        assert len(await repo.get_parcels_by_user_id(owner, paginate_rate=3)) == 3
        assert len(await repo.get_parcels_by_user_id(owner, paginate_rate=100)) == 8

    async def test_name_filter_is_case_insensitive_substring(
        self, repo: SqlAlchemyParcelRepository, parcel_types: list[ParcelType]
    ) -> None:
        owner = uuid.uuid4()
        for name in ("Red Book", "blue BOOK", "Laptop"):
            await repo.save_parcel(
                make_parcel(user_id=owner, name=name, parcel_type=parcel_types[0])
            )

        result = await repo.get_parcels_by_user_id(owner, p_filter="book")

        assert sorted(p.name for p in result) == ["Red Book", "blue BOOK"]

    async def test_filter_wildcards_are_not_special(
        self, repo: SqlAlchemyParcelRepository, parcel_types: list[ParcelType]
    ) -> None:
        owner = uuid.uuid4()
        await repo.save_parcel(make_parcel(user_id=owner, name="Book", parcel_type=parcel_types[0]))

        assert await repo.get_parcels_by_user_id(owner, p_filter="zzz") == []


class TestGetActiveParcels:
    async def test_only_active_parcels(
        self, repo: SqlAlchemyParcelRepository, parcel_types: list[ParcelType]
    ) -> None:
        active = make_parcel(parcel_type=parcel_types[0])
        paid = make_parcel(parcel_type=parcel_types[0], status=ParcelStatus.IN_DELIVERY)
        canceled = make_parcel(parcel_type=parcel_types[0], status=ParcelStatus.CANCELED)
        for parcel in (active, paid, canceled):
            await repo.save_parcel(parcel)

        result = await repo.get_active_parcels()

        assert [p.id for p in result] == [active.id]

    async def test_ordered_by_id(
        self, repo: SqlAlchemyParcelRepository, parcel_types: list[ParcelType]
    ) -> None:
        parcels = [make_parcel(parcel_type=parcel_types[0]) for _ in range(6)]
        for parcel in parcels:
            await repo.save_parcel(parcel)

        result = await repo.get_active_parcels()

        assert [p.id for p in result] == sorted(p.id for p in parcels)

    async def test_keyset_pagination_visits_every_parcel_once(
        self, repo: SqlAlchemyParcelRepository, parcel_types: list[ParcelType]
    ) -> None:
        parcels = [make_parcel(parcel_type=parcel_types[0]) for _ in range(7)]
        for parcel in parcels:
            await repo.save_parcel(parcel)

        seen: list[uuid.UUID] = []
        after: uuid.UUID | None = None
        while batch := await repo.get_active_parcels(limit=3, after_id=after):
            assert len(batch) <= 3
            seen.extend(p.id for p in batch)
            after = batch[-1].id

        assert seen == sorted(p.id for p in parcels)

    async def test_after_id_is_exclusive(
        self, repo: SqlAlchemyParcelRepository, parcel_types: list[ParcelType]
    ) -> None:
        parcels = [make_parcel(parcel_type=parcel_types[0]) for _ in range(3)]
        for parcel in parcels:
            await repo.save_parcel(parcel)
        ordered = sorted(p.id for p in parcels)

        result = await repo.get_active_parcels(after_id=ordered[0])

        assert [p.id for p in result] == ordered[1:]


class TestSaveParcels:
    async def test_bulk_update(
        self,
        repo: SqlAlchemyParcelRepository,
        session: AsyncSession,
        parcel_types: list[ParcelType],
    ) -> None:
        parcels = [make_parcel(parcel_type=parcel_types[0]) for _ in range(3)]
        for parcel in parcels:
            await repo.save_parcel(parcel)

        loaded = await repo.get_active_parcels()
        for parcel in loaded:
            parcel.calculate_delivery_cost(Decimal("100"))
        await repo.save_parcels(loaded)
        session.expire_all()

        assert all(
            p.delivery_cost_rub == Decimal("110.00") for p in await repo.get_active_parcels()
        )

    async def test_unknown_parcels_are_skipped(
        self, repo: SqlAlchemyParcelRepository, parcel_types: list[ParcelType]
    ) -> None:
        ghost = make_parcel(parcel_type=parcel_types[0])

        await repo.save_parcels([ghost])

        assert await repo.get_parcel_by_id(ghost.id) is None

    async def test_status_written_by_someone_else_is_not_overwritten(
        self,
        session_factory: object,
        repo: SqlAlchemyParcelRepository,
        parcel_types: list[ParcelType],
    ) -> None:
        """The user pays (status -> in_delivery) while the job is calculating the same parcel."""
        parcel = make_parcel(parcel_type=parcel_types[0])
        await repo.save_parcel(parcel)
        [job_copy] = await repo.get_active_parcels()

        async with session_factory() as other_session:  # type: ignore[operator]
            other_repo = SqlAlchemyParcelRepository(other_session)
            paid = await other_repo.get_parcel_by_id(parcel.id)
            assert paid is not None
            paid.status = ParcelStatus.IN_DELIVERY
            await other_repo.save_parcel(paid)

        job_copy.calculate_delivery_cost(Decimal("90"))
        await repo.save_parcels([job_copy])

        async with session_factory() as check_session:  # type: ignore[operator]
            final = await SqlAlchemyParcelRepository(check_session).get_parcel_by_id(parcel.id)
        assert final is not None
        assert final.status is ParcelStatus.IN_DELIVERY  # not reverted to ACTIVE
        assert final.delivery_cost_rub == Decimal("0")  # the price is frozen at the paid state
