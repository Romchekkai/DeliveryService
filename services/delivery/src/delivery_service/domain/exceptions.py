class DomainError(Exception):
    """Base class for exceptions in delivery domain module."""


class ParcelEmptyNameError(DomainError):
    pass


class ParcelIncorrectWeightError(DomainError):
    pass


class ParcelIncorrectPriceError(DomainError):
    pass


class ParcelDeliveryCalculationPriceError(DomainError):
    pass


class ParcelNotFoundError(DomainError):
    pass


class ParcelTypeNotFoundError(DomainError):
    pass


class CurrencyRateUnavailableError(DomainError):
    pass
