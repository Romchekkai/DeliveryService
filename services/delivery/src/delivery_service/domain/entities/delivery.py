import uuid
from dataclasses import dataclass
from uuid import UUID

from delivery_service.domain.entities.parcel import Parcel
from delivery_service.domain.value_objects.delivery_status import DeliveryStatus
from delivery_service.domain.value_objects.parcel_status import ParcelStatus


@dataclass
class Delivery:
    id: UUID
    parcels: list[Parcel]
    status: DeliveryStatus
    price_rub: int

    @classmethod
    def register_delivery(cls, parcels: list[Parcel]) -> "Delivery":
        if not parcels:
            raise ValueError("No parcels provided")
        return cls(
            id=uuid.uuid4(),
            parcels=parcels,
            status=DeliveryStatus.CREATED,
            price_rub=500,
        )

    def add_parcel(self, parcel: Parcel) -> None:
        if not parcel:
            raise ValueError("No parcel provided")
        if parcel.status == ParcelStatus.CANCELED:
            raise ValueError("Parcel already canceled")
        self.parcels.append(parcel)
