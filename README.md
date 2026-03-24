# data-contracts-service

Инфраструктурный сервис управления Data Contracts для контрактно-ориентированной интеграции данных.

Сервис хранит и версионирует контракты, валидирует JSON Schema, проверяет совместимость версий и публикует активную версию контракта для потребителей.

## Основные возможности

- CRUD контрактов данных (`namespace + name` уникальны)
- Версионирование контрактов (`SemVer`)
- Promote/deprecate версий
- Валидация схемы контракта в формате JSON Schema Draft 2020-12
- Проверка совместимости (`backward`, `forward`, `full`) между версиями схем
- Автоматический SemVer policy-check при создании новой версии:
  `PATCH` требует `full compatibility`, `MINOR` требует `backward compatibility`,
  `MAJOR` допускает breaking changes
- Генерация draft-контракта из существующей PostgreSQL таблицы (schema introspection)
- Публикация active/конкретной версии для ingestion/runtime
- Soft-delete (архивирование)
- OpenAPI/Swagger (`/docs`)
- Метрики (`/metrics`) и healthcheck (`/health`)

## Технологии

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Pydantic v2 + pydantic-settings
- pytest
- Docker / docker-compose

## Быстрый старт (Docker)

```bash
cp .env.example .env

docker compose up --build
```

После запуска:

- Swagger: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`
- Health: `http://localhost:8000/health`

## Переменные окружения

- `DATABASE_URL` — URL PostgreSQL
- `API_KEY` — ключ для всех non-GET endpoint'ов (заголовок `X-API-Key`)
- `DATA_CONTRACTS_LOG_LEVEL` — уровень логирования

Пример (`.env`):

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/data_contracts
API_KEY=dev-api-key
DATA_CONTRACTS_LOG_LEVEL=INFO
```

## Миграции

Применить миграции:

```bash
alembic upgrade head
```

Откатить на 1 шаг:

```bash
alembic downgrade -1
```

## Локальный запуск без Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/data_contracts
export API_KEY=dev-api-key

alembic upgrade head
uvicorn app.main:app --reload
```

## Тесты

```bash
pytest
```

Для integration-тестов нужен PostgreSQL (используется `TEST_DATABASE_URL`, по умолчанию `postgresql+psycopg://postgres:postgres@localhost:5432/data_contracts_test`).

## Безопасность

- Для всех non-GET endpoint обязателен `X-API-Key`
- Заголовок `X-Actor` используется как `created_by` (если отсутствует, используется `system`)

## Примеры curl

Ниже используется:

```bash
export BASE_URL=http://localhost:8000
export API_KEY=dev-api-key
```

### 1. Создать контракт

```bash
curl -X POST "$BASE_URL/contracts" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Actor: platform-admin" \
  -d '{
    "namespace": "sales",
    "name": "orders",
    "entity_name": "orders_table",
    "entity_type": "table",
    "description": "Orders contract",
    "owners": ["data-platform@company.local"],
    "tags": ["orders", "finance"],
    "target_layer": "curated"
  }'
```

### 2. Добавить версию контракта

```bash
curl -X POST "$BASE_URL/contracts/<CONTRACT_ID>/versions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Actor: platform-admin" \
  -d '{
    "version": "1.0.0",
    "compatibility_mode": "backward",
    "schema": {
      "$schema": "https://json-schema.org/draft/2020-12/schema",
      "type": "object",
      "properties": {
        "order_id": {"type": "string"},
        "amount": {"type": "integer"}
      },
      "required": ["order_id"],
      "additionalProperties": false,
      "x-primaryKey": ["order_id"],
      "x-businessKey": ["order_id"],
      "description": "v1"
    }
  }'
```

### 3. Проверить совместимость новой версии

```bash
curl -X POST "$BASE_URL/contracts/<CONTRACT_ID>/versions/1.1.0/compatibility" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Actor: platform-admin" \
  -d '{
    "base_version": "1.0.0",
    "mode": "backward"
  }'
```

### 4. Получить active-версию

```bash
curl "$BASE_URL/contracts/sales/orders/active"
```

## Генерация контракта из существующей таблицы

Эндпоинт `POST /introspect` подключается к PostgreSQL, считывает структуру таблицы (колонки + PK),
создаёт новый контракт в статусе `draft` и версию `0.1.0` в статусе `draft`.

```bash
curl -X POST "$BASE_URL/introspect" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -H "X-Actor: platform-admin" \
  -d '{
    "connection_string": "postgresql+psycopg://postgres:postgres@localhost:5432/source_db",
    "schema": "public",
    "table_name": "orders",
    "namespace": "erp",
    "name": "orders_contract",
    "entity_type": "table",
    "target_layer": "raw"
  }'
```

Ограничения introspection:

- поддерживается только PostgreSQL
- поддерживаются только таблицы (`BASE TABLE`), не `VIEW`
- если контракт с таким `namespace + name` уже есть, возвращается `409`
- если таблица не найдена, возвращается `404`
- `business` и `hash_keys` автоматически не заполняются

## Кратко о schema evolution

Поддерживаемые режимы:

- `backward`: нельзя удалять обязательные поля, нельзя несовместимо менять типы, можно добавлять nullable поля
- `forward`: нельзя удалять поля, нельзя добавлять обязательные поля
- `full`: объединение `backward + forward`
- `none`: проверки не блокируют изменения (`warn`)

Дополнительные правила:

- `nullable: true -> false` считается breaking change (`fail`)
- `int -> float` считается `warn`
- `string -> int` считается `fail`
