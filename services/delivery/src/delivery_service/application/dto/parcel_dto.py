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
    delivery_cost_rub: str


@dataclass(frozen=True)
class ParcelOutputDTO:
    id: UUID
    name: str
    weight_kg: float
    parcel_type: str
    content_cost_usd: Decimal
    delivery_cost_rub: str
    status: str


@dataclass(frozen=True)
class ParcelOutputShortDTO:
    name: str
    parcel_type: str
    delivery_cost_rub: str
