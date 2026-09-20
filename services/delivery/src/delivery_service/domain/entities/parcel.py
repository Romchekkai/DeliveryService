import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from delivery_service.domain.exceptions import (
    ParcelDeliveryCalculationPriceError,
    ParcelEmptyNameError,
    ParcelIncorrectPriceError,
    ParcelIncorrectWeightError,
)
from delivery_service.domain.value_objects.parcel_status import ParcelStatus

# @dataclass
# class WeightConstraint:
#     id: int
#     name: string
#     weight: float
MAX_WEIGHT_KG = 500


@dataclass
class ParcelType:
    id: int
    name: str


@dataclass
class Parcel:
    id: UUID
    user_id: UUID
    name: str
    weight_kg: float
    type: ParcelType
    content_cost_cents: int
    delivery_cost_rub: Decimal
    status: ParcelStatus

    @classmethod
    def register_parcel(
        cls, owner_id: UUID, name: str, weight: float, type_parcel: ParcelType, cont_cost: int
    ) -> "Parcel":
        if not name.strip():
            raise ParcelEmptyNameError("Parcel name cannot be empty")
        if weight <= 0 or weight > MAX_WEIGHT_KG:
            raise ParcelIncorrectWeightError("Parcel weight cannot be zero or negative")
        if cont_cost < 0:
            raise ParcelIncorrectPriceError("Parcel price cannot be negative")

        return cls(
            id=uuid.uuid4(),
            user_id=owner_id,
            name=name,
            weight_kg=weight,
            type=type_parcel,
            content_cost_cents=cont_cost,
            delivery_cost_rub=Decimal("0"),
            status=ParcelStatus.ACTIVE,
        )

    def cost_in_usd(self) -> Decimal:
        return Decimal(self.content_cost_cents) * Decimal("0.01")

    def change_type(self, new_type_parcel: ParcelType) -> None:
        self.type = new_type_parcel

    def cancel_parcel(self) -> None:
        self.status = ParcelStatus.CANCELED

    def is_delivery_cost_calculated(self) -> bool:
        return self.delivery_cost_rub > Decimal("0")

    def calculate_delivery_cost(self, currency_rate_rub: Decimal) -> None:
        if self.status != ParcelStatus.ACTIVE:
            raise ParcelDeliveryCalculationPriceError("Parcel status is not active")
        if currency_rate_rub <= Decimal("0"):
            raise ParcelDeliveryCalculationPriceError("Currency rate must be positive")
        base = Decimal(str(self.weight_kg)) * Decimal("0.5") + self.cost_in_usd() * Decimal("0.01")
        self.delivery_cost_rub = (base * currency_rate_rub).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


# rate = Decimal("84.17")
# standard = ParcelType(1, "standard")
# parcel = Parcel.register_parcel(uuid.uuid4(), "fff", 232.231, standard, 455)
#
# parcel.calculate_delivery_cost(rate)
# print(parcel.delivery_cost_rub)
