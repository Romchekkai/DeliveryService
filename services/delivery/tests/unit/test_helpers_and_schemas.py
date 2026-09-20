from decimal import Decimal

import pytest
from delivery_service.application.helpers import NOT_CALCULATED, format_delivery_cost
from delivery_service.presentation.api.schemas.parcel_schemas import ParcelCreateRequest
from pydantic import ValidationError


class TestFormatDeliveryCost:
    @pytest.mark.parametrize("value", [None, Decimal("0"), Decimal("0.00"), Decimal("-5")])
    def test_not_calculated(self, value: Decimal | None) -> None:
        assert format_delivery_cost(value) == NOT_CALCULATED == "Не рассчитано"

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (Decimal("99"), "99.00"),
            (Decimal("99.5"), "99.50"),
            (Decimal("9777.27"), "9777.27"),
            (Decimal("0.01"), "0.01"),
        ],
    )
    def test_formats_with_two_decimals(self, value: Decimal, expected: str) -> None:
        assert format_delivery_cost(value) == expected


class TestParcelCreateRequest:
    valid = {"name": "Book", "weight_kg": 1.5, "parcel_type_id": 1, "content_cost_cents": 100}

    def test_valid_payload(self) -> None:
        request = ParcelCreateRequest(**self.valid)

        assert request.weight_kg == 1.5

    @pytest.mark.parametrize(
        "override",
        [
            {"name": ""},
            {"name": "x" * 101},
            {"weight_kg": 0},
            {"weight_kg": -1},
            {"weight_kg": 500},
            {"content_cost_cents": -1},
            {"parcel_type_id": "abc"},
        ],
    )
    def test_invalid_payload(self, override: dict[str, object]) -> None:
        with pytest.raises(ValidationError):
            ParcelCreateRequest(**{**self.valid, **override})

    def test_boundaries(self) -> None:
        ParcelCreateRequest(**{**self.valid, "name": "x" * 100, "weight_kg": 499.999})
        ParcelCreateRequest(**{**self.valid, "content_cost_cents": 0})
