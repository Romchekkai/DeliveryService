from typing import Optional, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from delivery_service.domain.entities.parcel import ParcelType
from delivery_service.domain.repositories.parcel_type_repository import ParcelTypeRepository
from delivery_service.infrastructure.db.models.parcel_type_model import ParcelTypeModel


class SqlAlchemyParcelTypeRepository(ParcelTypeRepository):
    def __init__(self, async_session: AsyncSession):
        self._async_session = async_session

    async def get_parcel_types(self) -> list[ParcelType]:
        result = await self._async_session.execute(select(ParcelTypeModel))
        return [p_type.to_entity() for p_type in result.scalars().all()]

    async def get_parcel_by_id(self, parcel_type_id: int) -> Optional[ParcelType]:
        model = cast(
            ParcelTypeModel | None, await self._async_session.get(ParcelTypeModel, parcel_type_id)
        )
        return model.to_entity() if model else None
