from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID

from delivery_service.domain.entities.parcel import Parcel


class ParcelRepository(ABC):
    @abstractmethod
    async def get_parcel_by_id(self, parcel_id: UUID) -> Optional[Parcel]: ...

    @abstractmethod
    async def get_parcels_by_user_id(
        self, user_id: UUID, paginate_rate: int = 5, p_filter: str = ""
    ) -> list[Parcel]: ...

    @abstractmethod
    async def save_parcel(self, parcel: Parcel) -> None: ...

    @abstractmethod
    async def get_active_parcels(
        self, limit: int = 500, after_id: Optional[UUID] = None
    ) -> list[Parcel]: ...

    @abstractmethod
    async def save_parcels(self, parcels: list[Parcel]) -> None: ...
