"""Small builders so tests stay readable."""

from __future__ import annotations

import uuid
from decimal import Decimal

from delivery_service.domain.entities.parcel import Parcel, ParcelType
from delivery_service.domain.value_objects.parcel_status import ParcelStatus

CLOTHES = ParcelType(id=1, name="Одежда")
ELECTRONICS = ParcelType(id=2, name="Электроника")
OTHER = ParcelType(id=3, name="Разное")


def make_parcel(
    *,
    user_id: uuid.UUID | None = None,
    name: str = "Parcel",
    weight_kg: float = 2.0,
    content_cost_cents: int = 1000,
    parcel_type: ParcelType = CLOTHES,
    delivery_cost_rub: Decimal = Decimal("0"),
    status: ParcelStatus = ParcelStatus.ACTIVE,
) -> Parcel:
    return Parcel(
        id=uuid.uuid4(),
        user_id=user_id or uuid.uuid4(),
        name=name,
        weight_kg=weight_kg,
        type=parcel_type,
        content_cost_cents=content_cost_cents,
        delivery_cost_rub=delivery_cost_rub,
        status=status,
    )
