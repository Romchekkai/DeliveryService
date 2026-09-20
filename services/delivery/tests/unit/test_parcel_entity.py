from decimal import Decimal
from uuid import uuid4

import pytest
from delivery_service.domain.entities.parcel import MAX_WEIGHT_KG, Parcel
from delivery_service.domain.exceptions import (
    ParcelDeliveryCalculationPriceError,
    ParcelEmptyNameError,
    ParcelIncorrectPriceError,
    ParcelIncorrectWeightError,
)
from delivery_service.domain.value_objects.parcel_status import ParcelStatus

from tests.factories import CLOTHES, ELECTRONICS, make_parcel


class TestRegisterParcel:
    def test_creates_active_parcel_with_zero_delivery_cost(self) -> None:
        owner = uuid4()

        parcel = Parcel.register_parcel(owner, "Book", 1.5, CLOTHES, 1200)

        assert parcel.user_id == owner
        assert parcel.name == "Book"
        assert parcel.weight_kg == 1.5
        assert parcel.type == CLOTHES
        assert parcel.content_cost_cents == 1200
        assert parcel.delivery_cost_rub == Decimal("0")
        assert parcel.status is ParcelStatus.ACTIVE
        assert not parcel.is_delivery_cost_calculated()

    def test_ids_are_unique(self) -> None:
        a = Parcel.register_parcel(uuid4(), "A", 1, CLOTHES, 0)
        b = Parcel.register_parcel(uuid4(), "B", 1, CLOTHES, 0)

        assert a.id != b.id

    @pytest.mark.parametrize("name", ["", "   ", "\t\n"])
    def test_empty_name_is_rejected(self, name: str) -> None:
        with pytest.raises(ParcelEmptyNameError):
            Parcel.register_parcel(uuid4(), name, 1, CLOTHES, 0)

    @pytest.mark.parametrize("weight", [0, -1, -0.001, MAX_WEIGHT_KG + 0.001, 10_000])
    def test_incorrect_weight_is_rejected(self, weight: float) -> None:
        with pytest.raises(ParcelIncorrectWeightError):
            Parcel.register_parcel(uuid4(), "P", weight, CLOTHES, 0)

    @pytest.mark.parametrize("weight", [0.001, 1, MAX_WEIGHT_KG])
    def test_boundary_weights_are_accepted(self, weight: float) -> None:
        assert Parcel.register_parcel(uuid4(), "P", weight, CLOTHES, 0).weight_kg == weight

    def test_negative_content_cost_is_rejected(self) -> None:
        with pytest.raises(ParcelIncorrectPriceError):
            Parcel.register_parcel(uuid4(), "P", 1, CLOTHES, -1)

    def test_zero_content_cost_is_allowed(self) -> None:
        assert Parcel.register_parcel(uuid4(), "P", 1, CLOTHES, 0).content_cost_cents == 0


class TestCostInUsd:
    @pytest.mark.parametrize(
        ("cents", "usd"),
        [(0, "0.00"), (1, "0.01"), (455, "4.55"), (100_000, "1000.00")],
    )
    def test_cents_are_converted_to_dollars(self, cents: int, usd: str) -> None:
        assert make_parcel(content_cost_cents=cents).cost_in_usd() == Decimal(usd)


class TestCalculateDeliveryCost:
    """cost = (weight_kg * 0.5 + content_usd * 0.01) * usd_rate_rub, rounded to kopecks."""

    def test_formula(self) -> None:
        parcel = make_parcel(weight_kg=2.0, content_cost_cents=1000)  # 2*0.5 + 10*0.01 = 1.10

        parcel.calculate_delivery_cost(Decimal("90"))

        assert parcel.delivery_cost_rub == Decimal("99.00")
        assert parcel.is_delivery_cost_calculated()

    def test_example_from_the_domain_module(self) -> None:
        parcel = make_parcel(weight_kg=232.231, content_cost_cents=455)

        parcel.calculate_delivery_cost(Decimal("84.17"))

        assert parcel.delivery_cost_rub == Decimal("9777.27")

    def test_result_has_kopeck_precision(self) -> None:
        parcel = make_parcel(weight_kg=1.234, content_cost_cents=333)

        parcel.calculate_delivery_cost(Decimal("77.7777"))

        assert parcel.delivery_cost_rub == parcel.delivery_cost_rub.quantize(Decimal("0.01"))

    def test_rounds_half_up(self) -> None:
        parcel = make_parcel(weight_kg=0.01, content_cost_cents=0)  # 0.005 RUB at rate 1

        parcel.calculate_delivery_cost(Decimal("1"))

        assert parcel.delivery_cost_rub == Decimal("0.01")  # banker's rounding would give 0.00

    def test_recalculation_with_a_new_rate_overwrites_the_cost(self) -> None:
        parcel = make_parcel(weight_kg=2.0, content_cost_cents=1000)

        parcel.calculate_delivery_cost(Decimal("90"))
        parcel.calculate_delivery_cost(Decimal("100"))

        assert parcel.delivery_cost_rub == Decimal("110.00")

    @pytest.mark.parametrize("status", [ParcelStatus.CANCELED, ParcelStatus.IN_DELIVERY])
    def test_only_active_parcels_are_calculated(self, status: ParcelStatus) -> None:
        parcel = make_parcel(status=status, delivery_cost_rub=Decimal("50.00"))

        with pytest.raises(ParcelDeliveryCalculationPriceError):
            parcel.calculate_delivery_cost(Decimal("90"))
        assert parcel.delivery_cost_rub == Decimal("50.00")

    @pytest.mark.parametrize("rate", ["0", "-1", "-84.17"])
    def test_rate_must_be_positive(self, rate: str) -> None:
        parcel = make_parcel()

        with pytest.raises(ParcelDeliveryCalculationPriceError):
            parcel.calculate_delivery_cost(Decimal(rate))
        assert parcel.delivery_cost_rub == Decimal("0")


class TestParcelMutations:
    def test_cancel_parcel(self) -> None:
        parcel = make_parcel()
        parcel.cancel_parcel()

        assert parcel.status is ParcelStatus.CANCELED

    def test_change_type(self) -> None:
        parcel = make_parcel(parcel_type=CLOTHES)
        parcel.change_type(ELECTRONICS)

        assert parcel.type == ELECTRONICS

    def test_canceled_parcel_can_not_be_calculated_anymore(self) -> None:
        parcel = make_parcel()
        parcel.cancel_parcel()

        with pytest.raises(ParcelDeliveryCalculationPriceError):
            parcel.calculate_delivery_cost(Decimal("90"))
