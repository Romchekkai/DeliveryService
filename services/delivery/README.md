# Delivery Service

Регистрация посылок и расчёт стоимости доставки.

- `POST /api/v1/parcels` — создать посылку (нужен Bearer-токен users-сервиса)
- `GET  /api/v1/parcels` — свои посылки
- `GET  /api/v1/parcels/types` — типы посылок
- `GET  /api/v1/parcels/{id}` — посылка по id (только своя)
- `POST /api/v1/admin/tasks/calculate-costs` — запуск расчёта вне расписания (роль admin)
- `GET  /api/v1/admin/tasks` — список задач и время следующего запуска
- `GET  /metrics` — метрики Prometheus

Стоимость = (вес кг * 0.5 + содержимое в $ * 0.01) * курс USD/RUB.
Курс берётся с cbr-xml-daily.ru и кэшируется в Redis.
Пока стоимость не рассчитана — в выдаче `"Не рассчитано"`.
