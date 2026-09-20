from prometheus_client import Counter, Gauge, Histogram

# Метрики периодической задачи — Prometheus скрейпит их с /metrics
parcels_calculated_total = Counter(
    "delivery_parcels_calculated_total",
    "Количество посылок, которым проставлена стоимость доставки",
)

calculation_runs_total = Counter(
    "delivery_calculation_runs_total",
    "Количество запусков задачи расчёта стоимости",
    ["trigger", "result"],  # trigger: scheduler|manual, result: success|error
)

calculation_duration_seconds = Histogram(
    "delivery_calculation_duration_seconds",
    "Длительность выполнения задачи расчёта стоимости",
)

usd_rate_rub = Gauge(
    "delivery_usd_rate_rub",
    "Текущий курс доллара к рублю, использованный при расчёте",
)

fx_rate_requests_total = Counter(
    "delivery_fx_rate_requests_total",
    "Обращения за курсом доллара",
    ["source"],  # cache|cbr
)
