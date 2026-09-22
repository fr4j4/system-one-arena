# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm AS base
COPY --from=ghcr.io/astral-sh/uv:0.11.17 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 ARENA_DATA_DIR=/app/data ARENA_FRONTEND_DIR=/app/frontend/dist
COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
RUN uv sync --frozen --no-dev
COPY --from=ui /ui/dist ./frontend/dist
RUN useradd --create-home --uid 10001 arena && mkdir -p /app/data /app/models && chown -R arena:arena /app
ENV PATH="/app/.venv/bin:$PATH" HF_HOME=/app/models USE_TF=0
USER arena
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=2)"
CMD ["uvicorn", "arena.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS cpu
USER root
COPY requirements-cpu.lock ./
RUN uv pip sync --python /app/.venv/bin/python --torch-backend cpu requirements-cpu.lock && uv pip install --python /app/.venv/bin/python --no-deps .
ENV LAYA_ENABLED=true LAYA_DEVICE=cpu
USER arena

FROM base AS cuda
USER root
RUN uv sync --frozen --no-dev --extra laya
ENV LAYA_ENABLED=true LAYA_DEVICE=cuda
USER arena
