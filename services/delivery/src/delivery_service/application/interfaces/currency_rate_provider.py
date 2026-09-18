from abc import ABC, abstractmethod
from decimal import Decimal


class CurrencyRateProvider(ABC):
    @abstractmethod
    async def get_usd_rate(self) -> Decimal: ...
