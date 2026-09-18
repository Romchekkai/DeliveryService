from typing import Optional
from uuid import UUID

from delivery_service.application.dto.parcel_dto import ParcelOutputDTO
from delivery_service.application.helpers import format_delivery_cost
from delivery_service.domain.exceptions import ParcelNotFoundError
from delivery_service.domain.repositories.parcel_repository import ParcelRepository


class GetParcelsByIdUseCase:
    def __init__(self, parcel_repository: ParcelRepository):
        self._parcel_repository = parcel_repository

    async def execute(self, parcel_id: UUID, user_id: UUID) -> Optional[ParcelOutputDTO]:
        parcel = await self._parcel_repository.get_parcel_by_id(parcel_id)

        if parcel is None or parcel.user_id != user_id:
            raise ParcelNotFoundError(f"Посылка {parcel_id} не найдена")

        return ParcelOutputDTO(
            id=parcel.id,
            name=parcel.name,
            weight_kg=parcel.weight_kg,
            parcel_type=parcel.type.name,
            content_cost_usd=parcel.cost_in_usd(),
            delivery_cost_rub=format_delivery_cost(parcel.delivery_cost_rub),
            status=parcel.status.value,
        )
