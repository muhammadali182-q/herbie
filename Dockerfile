FROM ghcr.io/astral-sh/uv:0.11.26 AS uv

FROM python:3.12-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN groupadd --system --gid 10001 herbie \
    && useradd --system --uid 10001 --gid herbie --home-dir /app herbie

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY backend ./backend

RUN uv sync --frozen --no-dev

USER herbie

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"]

CMD ["uvicorn", "herbie.main:app", "--host", "0.0.0.0", "--port", "8000"]
