SHELL := /bin/bash

.DEFAULT_GOAL := help

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
UVICORN ?= .venv/bin/uvicorn
PYTEST ?= .venv/bin/pytest
ALEMBIC ?= .venv/bin/alembic
DOCKER_COMPOSE ?= docker compose

APP_MODULE ?= app.main:app
HOST ?= 0.0.0.0
PORT ?= 8000
MSG ?=

.PHONY: help venv install run run-prod docker-build compose-build compose-up compose-down compose-logs compose-ps alembic-revision alembic-upgrade alembic-downgrade lint typecheck package clean-dist test test-unit test-integration

help:
	@echo "Available targets:"
	@echo "  venv               - create local .venv"
	@echo "  install            - install prod+dev dependencies into .venv"
	@echo "  run                - run FastAPI locally with reload"
	@echo "  run-prod           - run FastAPI locally without reload"
	@echo "  docker-build       - build service Docker image"
	@echo "  compose-build      - build docker compose services"
	@echo "  compose-up         - start compose stack (postgres + service)"
	@echo "  compose-down       - stop compose stack"
	@echo "  compose-logs       - follow compose logs"
	@echo "  compose-ps         - show compose services status"
	@echo "  alembic-revision   - create Alembic revision (usage: make alembic-revision MSG=\"desc\")"
	@echo "  alembic-upgrade    - apply migrations to head"
	@echo "  alembic-downgrade  - rollback one migration"
	@echo "  lint               - run flake8 checks"
	@echo "  typecheck          - run mypy checks"
	@echo "  package            - build wheel and sdist"
	@echo "  clean-dist         - remove build artifacts"
	@echo "  test               - run all tests"
	@echo "  test-unit          - run unit tests only"
	@echo "  test-integration   - run integration tests only"

venv:
	python3 -m venv .venv

install:
	$(PIP) install -r requirements.txt -r requirements-dev.txt

run:
	$(UVICORN) $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

run-prod:
	$(UVICORN) $(APP_MODULE) --host $(HOST) --port $(PORT)

docker-build:
	docker build -t data-contracts-service:local .

compose-build:
	$(DOCKER_COMPOSE) build

compose-up:
	$(DOCKER_COMPOSE) up --build

compose-down:
	$(DOCKER_COMPOSE) down

compose-logs:
	$(DOCKER_COMPOSE) logs -f

compose-ps:
	$(DOCKER_COMPOSE) ps

alembic-revision:
	@if [ -z "$(MSG)" ]; then \
		echo "MSG is required. Example: make alembic-revision MSG=\"add contracts table\""; \
		exit 1; \
	fi
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

alembic-upgrade:
	$(ALEMBIC) upgrade head

alembic-downgrade:
	$(ALEMBIC) downgrade -1

lint:
	$(PYTHON) -m flake8 app tests scripts

typecheck:
	$(PYTHON) -m mypy app

package: clean-dist
	$(PYTHON) -m build

clean-dist:
	rm -rf build dist
	find . -maxdepth 1 -type d -name "*.egg-info" -exec rm -rf {} +

test:
	$(PYTEST)

test-unit:
	$(PYTEST) tests/unit

test-integration:
	$(PYTEST) tests/integration
