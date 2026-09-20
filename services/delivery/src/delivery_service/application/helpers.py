from decimal import Decimal
from typing import Optional

NOT_CALCULATED = "Не рассчитано"


def format_delivery_cost(cost: Optional[Decimal]) -> str:
    if cost is None or cost <= Decimal("0"):
        return NOT_CALCULATED
    return f"{cost:.2f}"
