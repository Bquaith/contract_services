SHELL := /bin/bash

.DEFAULT_GOAL := help

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
UVICORN ?= .venv/bin/uvicorn
PYTEST ?= .venv/bin/pytest
ALEMBIC ?= .venv/bin/alembic
DOCKER_COMPOSE ?= docker compose
DOCKER ?= docker

APP_MODULE ?= app.main:app
HOST ?= 0.0.0.0
PORT ?= 8000
MSG ?=
IMAGE_NAME ?= data-contracts-service:local
CONTAINER_NAME ?= contracts-service
HOST_PORT ?= 8000
CONTAINER_PORT ?= 8000
DOCKER_DATABASE_URL ?= postgresql+psycopg://postgres:postgres@host.docker.internal:5432/data_contracts
DOCKER_AUTH_ENABLED ?= false
DOCKER_EXTRA_HOST ?= host.docker.internal:host-gateway

.PHONY: help venv install run run-prod docker-build docker-run docker-restart docker-stop compose-build compose-up compose-down compose-logs compose-ps alembic-revision alembic-upgrade alembic-downgrade lint typecheck package clean-dist test test-unit test-integration

help:
	@echo "Available targets:"
	@echo "  venv               - create local .venv"
	@echo "  install            - install prod+dev dependencies into .venv"
	@echo "  run                - run FastAPI locally with reload"
	@echo "  run-prod           - run FastAPI locally without reload"
	@echo "  docker-build       - build service Docker image"
	@echo "  docker-run         - run service container in detached mode"
	@echo "  docker-restart     - restart service container"
	@echo "  docker-stop        - stop and remove service container"
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
	$(DOCKER) build -t $(IMAGE_NAME) .

docker-run: docker-build
	@$(DOCKER) rm -f $(CONTAINER_NAME) >/dev/null 2>&1 || true
	$(DOCKER) run -d \
		--name $(CONTAINER_NAME) \
		--restart unless-stopped \
		-p $(HOST_PORT):$(CONTAINER_PORT) \
		--add-host=$(DOCKER_EXTRA_HOST) \
		-e DATABASE_URL='$(DOCKER_DATABASE_URL)' \
		-e AUTH_ENABLED='$(DOCKER_AUTH_ENABLED)' \
		$(IMAGE_NAME)

docker-restart:
	$(DOCKER) restart $(CONTAINER_NAME)

docker-stop:
	@$(DOCKER) rm -f $(CONTAINER_NAME) >/dev/null 2>&1 || true

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
