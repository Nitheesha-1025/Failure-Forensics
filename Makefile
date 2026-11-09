.PHONY: help install test lint typecheck check fmt run serve docker clean

help:
	@echo "install     pip install -e .[dev]"
	@echo "test        pytest with coverage"
	@echo "lint        ruff check"
	@echo "typecheck   mypy --strict"
	@echo "check       lint + typecheck + test"
	@echo "fmt         ruff format + ruff check --fix"
	@echo "serve       forensics serve"
	@echo "docker      build the docker image"
	@echo "clean       caches + sqlite + traces dir"

install:
	python3 -m pip install -e ".[dev]"

test:
	pytest --cov

lint:
	ruff check src tests

typecheck:
	mypy src

check: lint typecheck test

fmt:
	ruff format src tests
	ruff check src tests --fix

serve:
	forensics serve

docker:
	docker build -t failure-forensics:local .

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov build dist *.egg-info
	rm -f forensics.sqlite3 forensics.sqlite3-*
	rm -rf traces/
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
