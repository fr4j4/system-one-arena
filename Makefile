.PHONY: setup build run test lint dev gpu cpu
setup:
	uv sync --frozen --extra dev
	cd frontend && npm ci
build:
	cd frontend && npm run build
run:
	uv run --no-sync uvicorn arena.app:app --host 127.0.0.1 --port 8000
dev:
	cd frontend && npm run dev
test:
	uv run --no-sync pytest -q
lint:
	uv run --no-sync ruff check --config pyproject.toml backend
	uv run --no-sync ruff format --check --config pyproject.toml backend
	cd frontend && npx prettier --check src
cpu:
	docker compose --profile cpu up --build -d
gpu:
	docker compose --profile gpu up --build -d
