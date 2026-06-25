.PHONY: help install dev test lint run clean docker-up docker-down

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install -r requirements.txt

dev: ## Install dev dependencies
	pip install -r requirements.txt
	pip install pytest pytest-asyncio

test: ## Run all tests
	python -m pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	python -m pytest tests/unit/ -v --tb=short

test-smoke: ## Run smoke tests only
	python -m pytest tests/smoke/ -v --tb=short

lint: ## Lint all Python files
	@find . -name "*.py" -not -path "./.git/*" -not -path "*__pycache__*" -not -path "*node_modules*" -not -path "*/source/*" | xargs python -m py_compile

run: ## Start the orchestrator
	python orchestrator/app.py

clean: ## Clean build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache state/*.db state/chroma 2>/dev/null || true

docker-up: ## Start all services via docker-compose
	docker-compose up -d --build

docker-down: ## Stop all services
	docker-compose down

db-init: ## Initialize the database
	python -c "from database.session import init_db; init_db()"
