# Многоступенчатая сборка: в финальный образ едут только готовое окружение
# и код — без uv, без кэшей и без инструментов сборки.

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Зависимости отдельным слоем: правка кода не пересобирает окружение.
# --frozen запрещает молча менять uv.lock, --no-dev выкидывает pytest/ruff/mypy.
# Кэш uv монтируется на время команды и в слои образа не попадает.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Из этого же образа запускается Job с миграциями, поэтому alembic едет внутрь.
COPY alembic.ini ./
COPY alembic ./alembic

ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Непривилегированный пользователь: процесс в контейнере не должен быть root.
USER 1000

EXPOSE 8000
CMD ["uvicorn", "adlex.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
