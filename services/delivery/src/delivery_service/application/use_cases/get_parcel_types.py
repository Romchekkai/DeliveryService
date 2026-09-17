from delivery_service.application.dto.parcel_type_dto import ParcelTypeOutputDTO
from delivery_service.domain.repositories.parcel_type_repository import ParcelTypeRepository


class GetParcelTypesUseCase:
    def __init__(self, parcel_types_repo: ParcelTypeRepository):
        self._parcel_types_repo = parcel_types_repo

    async def execute(self) -> list[ParcelTypeOutputDTO]:
        parcel_types = await self._parcel_types_repo.get_parcel_types()
        parcel_type_outputs: list[ParcelTypeOutputDTO] = []
        for p_type in parcel_types:
            parcel_type_outputs.append(
                ParcelTypeOutputDTO(
                    id=p_type.id,
                    name=p_type.name,
                )
            )

        return parcel_type_outputs
