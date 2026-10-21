.PHONY: help install install-core api ui test test-cov lint format format-check seed reset-db demo-video clean

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
PORT ?= 8000

help:  ## Show this help
	@echo "porchPiracyAI - available targets"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install all dependencies (including the heavy vision extras)
	$(PIP) install -r requirements.txt

install-core:  ## Install the core dependencies only (no OpenCV/Ultralytics)
	$(PIP) install -r requirements-core.txt

api:  ## Run the FastAPI backend with reload on port 8000
	$(PYTHON) -m uvicorn main:app --reload --port $(PORT)

ui:  ## Run the Streamlit dashboard
	$(PYTHON) -m streamlit run app.py

test:  ## Run the test suite
	$(PYTHON) -m pytest -q

test-cov:  ## Run the test suite with a coverage report
	$(PYTHON) -m pytest --cov=backend --cov-report=term-missing

lint:  ## Lint and check formatting
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:  ## Auto-format the code and fix lint issues
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

seed:  ## Load samples/mock_events.json into the database
	$(PYTHON) -m scripts.seed_database

reset-db:  ## Delete and recreate the SQLite database
	$(PYTHON) -m scripts.reset_database

clean:  ## Remove caches and generated data
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
