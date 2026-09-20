from typing import Optional, cast
from uuid import UUID

from sqlalchemy import Table, bindparam, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from delivery_service.domain.entities.parcel import Parcel
from delivery_service.domain.repositories.parcel_repository import ParcelRepository
from delivery_service.domain.value_objects.parcel_status import ParcelStatus
from delivery_service.infrastructure.db.models.parcel_model import ParcelModel


class SqlAlchemyParcelRepository(ParcelRepository):
    def __init__(self, async_session: AsyncSession) -> None:
        self._async_session = async_session

    async def get_parcel_by_id(self, parcel_id: UUID) -> Optional[Parcel]:
        result = await self._async_session.execute(
            select(ParcelModel).where(ParcelModel.id == parcel_id)
        )
        parcel = result.unique().scalar_one_or_none()

        return parcel.to_entity() if parcel else None

    async def get_parcels_by_user_id(
        self, user_id: UUID, paginate_rate: int = 5, p_filter: str = ""
    ) -> list[Parcel]:

        query = select(ParcelModel).where(ParcelModel.user_id == user_id)
        if p_filter:
            query = query.where(ParcelModel.name.ilike(f"%{p_filter}%"))
        query = query.limit(paginate_rate)

        result = await self._async_session.execute(query)
        parcels = result.unique().scalars().all()

        return [parcel.to_entity() for parcel in parcels]

    async def save_parcel(self, parcel: Parcel) -> None:
        result = cast(ParcelModel | None, await self._async_session.get(ParcelModel, parcel.id))
        if result is None:
            model = ParcelModel.from_entity(parcel)
            self._async_session.add(model)
        else:
            self._map_entity(result, parcel)

        await self._async_session.commit()

    async def get_active_parcels(
        self, limit: int = 500, after_id: Optional[UUID] = None
    ) -> list[Parcel]:
        query = select(ParcelModel).where(ParcelModel.status == ParcelStatus.ACTIVE)
        if after_id is not None:
            query = query.where(ParcelModel.id > after_id)
        query = query.order_by(ParcelModel.id).limit(limit)

        result = await self._async_session.execute(query)
        parcels = result.unique().scalars().all()
        return [parcel.to_entity() for parcel in parcels]

    async def save_parcels(self, parcels: list[Parcel]) -> None:
        if not parcels:
            return

        table = cast(Table, ParcelModel.__table__)
        await self._async_session.execute(
            update(table)
            .where(table.c.id == bindparam("parcel_id"), table.c.status == ParcelStatus.ACTIVE)
            .values(delivery_cost_rub=bindparam("cost")),
            [{"parcel_id": p.id, "cost": p.delivery_cost_rub or None} for p in parcels],
        )
        await self._async_session.commit()

    # async def save_parcels(self, parcels: list[Parcel]) -> None:
    #     for parcel in parcels:
    #         model = cast
    #         (ParcelModel | None, await self._async_session.get
    #         (ParcelModel, parcel.id))
    #         if model is None:
    #             continue
    #         else:
    #             self._map_entity(model, parcel)
    #
    #     await self._async_session.commit()

    @staticmethod
    def _map_entity(model: ParcelModel, parcel: Parcel) -> None:
        model.user_id = parcel.user_id
        model.name = parcel.name
        model.weight_kg = parcel.weight_kg
        model.type_id = parcel.type.id
        model.content_cost_cents = parcel.content_cost_cents
        model.delivery_cost_rub = parcel.delivery_cost_rub or None
        model.status = parcel.status
