from enum import Enum


class DeliveryStatus(str, Enum):
    IN_DELIVERY = "in_delivery"
    CREATED = "created"
    CANCELED = "canceled"
