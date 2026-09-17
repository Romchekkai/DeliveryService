from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from delivery_service.domain.entities.parcel import Parcel
from delivery_service.domain.repositories.parcel_repository import ParcelRepository
from delivery_service.infrastrucrure.db.models.parcel_model import ParcelModel
from delivery_service.infrastrucrure.db.models.parcel_type_model import ParcelTypeModel


class SqlAlchemyParcelRepository(ParcelRepository):
    def __init__(self, async_session: AsyncSession):
        self._async_session = async_session

    async def get_parcel_by_id(self, parcel_id: UUID) -> Optional[Parcel]:
        result = await self._async_session.execute(
            select(ParcelModel).where(ParcelModel.id == parcel_id)
        )
        parcel = result.scalar_one_or_none()

        return parcel.to_entity() if parcel else None

    async def get_parcels_by_user_id(
        self, user_id: UUID, paginate_rate: int = 5, p_filter: str = ""
    ) -> list[Parcel]:
        result = await self._async_session.execute(
            select(ParcelModel).where(ParcelModel.user_id == user_id)
        )
        parcels = result.scalars().all()

        entity_parcels: list[Parcel] = []
        for parcel in parcels:
            entity_parcels.append(parcel.to_entity())

        return entity_parcels

    async def save_parcel(self, parcel: Parcel) -> None:
        result = await self._async_session.get(ParcelModel, parcel.id)

        if result is None:
            model = ParcelModel.from_entity(parcel)
            self._async_session.add(model)
        else:
            result.id = parcel.id
            result.user_id = parcel.user_id
            result.name = parcel.name
            result.weight_kg = parcel.weight_kg
            result.type = ParcelTypeModel.from_entity(parcel.type)
            result.content_cost_cents = parcel.content_cost_cents
            result.delivery_cost_rub = parcel.delivery_cost_rub
            result.status = parcel.status
            await self._async_session.commit()
