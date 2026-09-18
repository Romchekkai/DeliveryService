from uuid import UUID

from delivery_service.application.dto.parcel_dto import ParcelOutputShortDTO
from delivery_service.application.helpers import format_delivery_cost
from delivery_service.domain.repositories.parcel_repository import ParcelRepository


class GetParcelsByUserUseCase:
    def __init__(self, parcel_repository: ParcelRepository):
        self._parcel_repository = parcel_repository

    async def execute(
        self, user_id: UUID, paginate_rate: int = 5, p_filter: str = ""
    ) -> list[ParcelOutputShortDTO]:
        parcels = await self._parcel_repository.get_parcels_by_user_id(
            user_id, paginate_rate, p_filter
        )
        parcel_outputs: list[ParcelOutputShortDTO] = []
        for parcel in parcels:
            parcel_outputs.append(
                ParcelOutputShortDTO(
                    name=parcel.name,
                    parcel_type=parcel.type.name,
                    delivery_cost_rub=format_delivery_cost(parcel.delivery_cost_rub),
                )
            )

        return parcel_outputs
