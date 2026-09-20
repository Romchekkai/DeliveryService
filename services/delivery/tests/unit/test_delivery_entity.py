import pytest
from delivery_service.domain.entities.delivery import Delivery
from delivery_service.domain.value_objects.delivery_status import DeliveryStatus

from tests.factories import make_parcel


def test_register_delivery() -> None:
    parcels = [make_parcel(), make_parcel()]

    delivery = Delivery.register_delivery(parcels)

    assert delivery.parcels == parcels
    assert delivery.status is DeliveryStatus.CREATED
    assert delivery.price_rub == 500


def test_register_delivery_without_parcels_raises() -> None:
    with pytest.raises(ValueError):
        Delivery.register_delivery([])


def test_add_parcel() -> None:
    delivery = Delivery.register_delivery([make_parcel()])
    extra = make_parcel()

    delivery.add_parcel(extra)

    assert delivery.parcels[-1] is extra
    assert len(delivery.parcels) == 2


def test_add_canceled_parcel_raises() -> None:
    delivery = Delivery.register_delivery([make_parcel()])
    canceled = make_parcel()
    canceled.cancel_parcel()

    with pytest.raises(ValueError, match="canceled"):
        delivery.add_parcel(canceled)
    assert len(delivery.parcels) == 1
