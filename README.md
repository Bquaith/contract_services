# data-contracts-service

Инфраструктурный сервис управления Data Contracts для контрактно-ориентированной интеграции данных.

Сервис хранит и версионирует контракты, валидирует схемы, проверяет совместимость версий и публикует активную версию контракта для потребителей.

## Основные возможности

- CRUD контрактов данных (`namespace + name` уникальны)
- Версионирование контрактов (`SemVer`)
- Promote/deprecate версий
- Валидация схемы контракта
- Проверка совместимости (`backward`, `forward`, `full`, `none`)
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

## Структура репозитория

```text
.
├── app
│   ├── api
│   │   ├── deps.py
│   │   ├── errors.py
│   │   ├── metrics.py
│   │   └── routers
│   │       ├── contracts.py
│   │       ├── publish.py
│   │       ├── system.py
│   │       └── validation.py
│   ├── compatibility
│   │   ├── diff.py
│   │   └── rules.py
│   ├── config
│   │   └── settings.py
│   ├── db
│   │   ├── base.py
│   │   ├── models.py
│   │   └── session.py
│   ├── logging
│   │   └── setup.py
│   ├── schemas
│   │   ├── common.py
│   │   ├── contract.py
│   │   ├── enums.py
│   │   ├── validation.py
│   │   └── version.py
│   ├── service
│   │   ├── compatibility.py
│   │   ├── contracts.py
│   │   ├── utils.py
│   │   ├── validation.py
│   │   └── versions.py
│   ├── validators
│   │   └── contract_schema.py
│   └── main.py
├── alembic
│   ├── env.py
│   ├── script.py.mako
│   └── versions
│       └── 0001_initial.py
├── docs
│   └── adr
│       ├── 0001-fastapi-postgresql.md
│       └── 0002-jsonb-semver.md
├── tests
│   ├── integration
│   │   └── test_api.py
│   ├── unit
│   │   ├── test_compatibility.py
│   │   └── test_schema_validator.py
│   └── conftest.py
├── .env.example
├── .github/workflows/ci.yml
├── alembic.ini
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── pytest.ini
├── requirements-dev.txt
└── requirements.txt
```

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
      "fields": [
        {"name": "order_id", "type": "string", "nullable": false},
        {"name": "amount", "type": "int", "nullable": true}
      ],
      "keys": {
        "primary": ["order_id"],
        "business": ["order_id"],
        "partition": [],
        "hash_keys": ["order_id"]
      },
      "constraints": [],
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

## CI

GitHub Actions (`.github/workflows/ci.yml`):

- поднимает PostgreSQL service
- применяет миграции
- запускает `pytest`
