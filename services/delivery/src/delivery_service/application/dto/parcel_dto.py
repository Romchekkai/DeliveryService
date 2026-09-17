from decimal import Decimal
from uuid import UUID

from pydantic.dataclasses import dataclass

from delivery_service.domain.entities.parcel import ParcelType


@dataclass(frozen=True)
class ParcelInputDTO:
    user_id: UUID
    name: str
    weight: float
    parcel_type_id: int
    content_cost_cents: int


@dataclass(frozen=True)
class ParcelCreateOutputDTO:
    id: UUID
    name: str
    parcel_type: ParcelType
    delivery_cost_rub: Decimal


@dataclass(frozen=True)
class ParcelOutputDTO:
    name: str
    parcel_type: str
    delivery_cost_rub: Decimal
