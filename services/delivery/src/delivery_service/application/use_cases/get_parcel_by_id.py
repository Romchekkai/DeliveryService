from typing import Optional
from uuid import UUID

from delivery_service.application.dto.parcel_dto import ParcelOutputDTO
from delivery_service.domain.repositories.parcel_repository import ParcelRepository


class GetParcelsByIdUseCase:
    def __init__(self, parcel_repository: ParcelRepository):
        self._parcel_repository = parcel_repository

    async def execute(self, parcel_id: UUID) -> Optional[ParcelOutputDTO]:
        parcel = await self._parcel_repository.get_parcel_by_id(parcel_id)

        if parcel is None:
            return None

        return ParcelOutputDTO(
            name=parcel.name,
            parcel_type=parcel.type.name,
            delivery_cost_rub=parcel.delivery_cost_rub,
        )
