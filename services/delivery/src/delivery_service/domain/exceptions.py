class DomainError(Exception):
    """Base class for exceptions in user domain module."""


class ParcelEmptyNameError(DomainError):
    pass


class ParcelIncorrectWeightError(DomainError):
    pass


class ParcelIncorrectPriceError(DomainError):
    pass


class ParcelDeliveryCalculationPriceError(DomainError):
    pass
