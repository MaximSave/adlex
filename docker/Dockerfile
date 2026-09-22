FROM python:3.12-slim

# uv кладём бинарником из официального образа — без pip и лишних слоёв
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Сначала зависимости, отдельным слоём: правка кода не пересобирает окружение.
# --frozen запрещает молча менять uv.lock, --no-dev выкидывает pytest/ruff/mypy.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Потом код и установка самого пакета adlex
COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --create-home app && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "adlex.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
