.PHONY: install test test-unit test-integration test-e2e test-all run migrate fmt lint

install:
	pip install -e ".[dev]"

test test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v

test-e2e:
	pytest tests/e2e -v

test-all:
	pytest -v

migrate:
	alembic upgrade head

run:
	uvicorn nup_pipeline.api.app:app --reload

fmt:
	ruff format src tests

lint:
	ruff check src tests
	mypy src
