# DeliveryService

## Запуск

```bash
docker compose up -d --build
docker compose ps   # все — running/healthy, vault-init — exited (0)
docker exec -it ollama ollama pull llama3.1
```

| Сервис | URL |
|---|---|
| users | http://localhost:8000/docs |
| delivery | http://localhost:8001/docs |
| support | http://localhost:8002/docs |
| grafana | http://localhost:3000 (admin/admin) |
| prometheus | http://localhost:9090 |

## Создать пользователя

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"StrongPass123!"}'
```

Активировать (новый юзер = `pending`) и выдать `admin` (нужен для ручного расчёта стоимости):

```bash
docker exec -it postgres-users psql -U postgres -d user_service_db -c \
  "UPDATE users SET status='ACTIVE', role='ADMIN' WHERE email='test@example.com';"
```

## Авторизоваться

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"StrongPass123!"}'
```

```bash
TOKEN="<access_token из ответа>"
```

## Создать посылку

```bash
curl -X POST http://localhost:8001/api/v1/parcels \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Ноутбук","weight_kg":2.5,"parcel_type_id":2,"content_cost_cents":100000}'
```

`parcel_type_id`: 1 — одежда, 2 — электроника, 3 — разное. `delivery_cost_rub` пока `"Не рассчитано"`.

## Проверить пересчёт стоимости

Автоматически — раз в 5 минут. Вручную:

```bash
curl -X POST http://localhost:8001/api/v1/admin/tasks/calculate-costs \
  -H "Authorization: Bearer $TOKEN"

curl http://localhost:8001/api/v1/parcels -H "Authorization: Bearer $TOKEN"
```

`delivery_cost_rub` = `(вес_кг * 0.5 + содержимое_$ * 0.01) * курс_USD_RUB`.

## Запрос в поддержку

```bash
curl -X POST http://localhost:8002/api/v1/support/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Можно ли отправить ноутбук?"}'
```

Первый запрос на CPU может занять несколько минут (инференс `llama3.1` без GPU). Для быстрой проверки — модель полегче:

```bash
docker exec -it ollama ollama pull llama3.2:1b
# в docker-compose.yml: LLM_MODEL: llama3.2:1b
docker compose up -d --build support
```

## Метрики и логи

Grafana → Explore:

- Prometheus: `delivery_parcels_calculated_total`, `delivery_calculation_runs_total`, `http_requests_total`
- Loki: `{service="users"}`, `{service="delivery"}`, `{service="support"}`

## Остановка

```bash
docker compose down       # -v — снести данные и модели
```
