from uuid import UUID

from delivery_service.application.dto.parcel_dto import ParcelOutputDTO
from delivery_service.domain.repositories.parcel_repository import ParcelRepository


class GetParcelsByUserUseCase:
    def __init__(self, parcel_repository: ParcelRepository):
        self._parcel_repository = parcel_repository

    async def execute(self, user_id: UUID) -> list[ParcelOutputDTO]:
        parcels = await self._parcel_repository.get_parcels_by_user_id(user_id)
        parcel_outputs: list[ParcelOutputDTO] = []
        for parcel in parcels:
            parcel_outputs.append(
                ParcelOutputDTO(
                    name=parcel.name,
                    parcel_type=parcel.type.name,
                    delivery_cost_rub=parcel.delivery_cost_rub,
                )
            )

        return parcel_outputs
