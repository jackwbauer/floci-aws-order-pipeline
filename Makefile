.PHONY: help up down bootstrap seed logs test lint fmt typecheck

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

up:  ## Start the whole stack (Floci, Postgres, API, workers)
	docker compose up -d --build

down:  ## Stop everything and remove volumes
	docker compose down -v

bootstrap:  ## (Re)provision AWS resources in a running Floci
	docker compose run --rm bootstrap

seed:  ## POST a sample order to the running API
	curl -sS -X POST http://localhost:8000/orders \
		-H 'content-type: application/json' \
		-d '{"customer_email":"buyer@distributor.com","items":[{"sku":"HELM-01","name":"Hard Hat","quantity":2,"unit_price_cents":3500}]}' | python -m json.tool

logs:  ## Tail service logs
	docker compose logs -f api invoice-worker reporting-worker

install:  ## Install all dependencies into a Poetry venv
	poetry install

test:  ## Run the full test suite (needs Docker for Testcontainers)
	pytest

lint:  ## Lint with ruff
	ruff check .

fmt:  ## Auto-format with ruff
	ruff format . && ruff check --fix .

typecheck:  ## Static types with mypy
	mypy
