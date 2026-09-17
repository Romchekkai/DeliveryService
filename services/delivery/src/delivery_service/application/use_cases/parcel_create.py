from delivery_service.application.dto.parcel_dto import ParcelCreateOutputDTO, ParcelInputDTO
from delivery_service.domain.entities.parcel import Parcel
from delivery_service.domain.repositories.parcel_repository import ParcelRepository
from delivery_service.domain.repositories.parcel_type_repository import ParcelTypeRepository


class CreateParcelUseCase:
    def __init__(
        self, parcel_repository: ParcelRepository, parcel_type_repository: ParcelTypeRepository
    ):
        self._parcel_repo = parcel_repository
        self._parcel_type_repo = parcel_type_repository

    async def execute(self, parcel_dto: ParcelInputDTO) -> ParcelCreateOutputDTO:
        type_parcel = self._parcel_type_repo.get_parcel_by_id(parcel_dto.parcel_type_id)

        parcel = Parcel.register_parcel(
            owner_id=parcel_dto.user_id,
            name=parcel_dto.name,
            weight=parcel_dto.weight,
            type_parcel=type_parcel,
            cont_cost=parcel_dto.content_cost_cents,
        )

        await self._parcel_repo.save_parcel(parcel)

        return ParcelCreateOutputDTO(
            id=parcel.id,
            name=parcel.name,
            parcel_type=parcel.type,
            delivery_cost_rub=parcel.delivery_cost_rub,
        )
