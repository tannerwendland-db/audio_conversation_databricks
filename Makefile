.PHONY: help install run test test-unit test-integration lint format migrate migrate-new clean bundle-deploy app-start app-deploy deploy

help:
	@echo "Audio Conversation RAG System - Available Commands"
	@echo "=================================================="
	@echo "install         Install dependencies using uv"
	@echo "run             Run the Dash application"
	@echo "test            Run all tests"
	@echo "test-unit       Run unit tests only"
	@echo "test-integration Run integration tests only"
	@echo "lint            Run ruff linting checks"
	@echo "format          Run ruff code formatter"
	@echo "migrate         Run database migrations (alembic upgrade head)"
	@echo "migrate-new     Create new migration (usage: make migrate-new MSG='description')"
	@echo "clean           Remove Python cache files and directories"
	@echo ""
	@echo "Deployment Commands"
	@echo "-------------------"
	@echo "bundle-deploy   Deploy the Databricks asset bundle"
	@echo "app-start       Start the Databricks app compute"
	@echo "app-deploy      Deploy the app source code to Databricks"
	@echo "deploy          Full deployment (bundle + migrate + start + deploy)"

venv:
	uv venv

install: venv
	uv pip install -r requirements.txt

run:
	PYTHONPATH=. uv run python src/app.py

test:
	uv run pytest tests/

test-unit:
	uv run pytest tests/unit/

test-integration:
	uv run pytest tests/integration/

lint:
	uv run ruff check .

format:
	uv run ruff format .

migrate:
	uv run alembic upgrade head

migrate-new:
	@if [ -z "$(MSG)" ]; then \
		echo "Error: MSG variable is required. Usage: make migrate-new MSG='your migration message'"; \
		exit 1; \
	fi
	uv run alembic revision --autogenerate -m "$(MSG)"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.py~" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf .venv

bundle-deploy:
	databricks bundle deploy

app-start:
	@APP_NAME=$$(databricks bundle summary -o json | jq -r '.resources.apps | to_entries | first | .value.name') && \
	COMPUTE_STATUS=$$(databricks apps get $$APP_NAME | jq -r '.compute_status.state') && \
	if [ "$$COMPUTE_STATUS" = "ACTIVE" ]; then \
		echo "App $$APP_NAME is already running"; \
	else \
		echo "Starting app $$APP_NAME..."; \
		databricks apps start "$$APP_NAME"; \
	fi

app-deploy:
	@APP_NAME=$$(databricks bundle summary -o json | jq -r '.resources.apps | to_entries | first | .value.name') && \
	WORKSPACE_PATH=$$(databricks bundle summary -o json | jq -r '.workspace.file_path') && \
	echo "Deploying app: $$APP_NAME from $$WORKSPACE_PATH" && \
	databricks apps deploy "$$APP_NAME" --source-code-path "$$WORKSPACE_PATH"

deploy: bundle-deploy migrate app-start app-deploy
	@echo "Deployment complete"
