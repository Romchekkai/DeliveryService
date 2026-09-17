from abc import ABC, abstractmethod

from delivery_service.domain.entities.parcel import ParcelType


class ParcelTypeRepository(ABC):
    @abstractmethod
    async def get_parcel_types(self) -> list[ParcelType]: ...

    @abstractmethod
    def get_parcel_by_id(self, parcel_type_id: int) -> ParcelType: ...
