from enum import Enum


class ParcelStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"
    IN_DELIVERY = "in_delivery"
