# AdLex

[![ci](https://github.com/MaximSave/adlex/actions/workflows/ci.yml/badge.svg)](https://github.com/MaximSave/adlex/actions/workflows/ci.yml)

Агентный сервис нормоконтроля рекламных материалов: отвечает на вопросы по рекламному
законодательству со ссылками на конкретные статьи, проверяет рекламный текст на нарушения
и собирает структуру лендинга с обязательными дисклеймерами.

Каждый ответ опирается на найденные фрагменты закона, а не на память модели: источник
цитаты можно открыть и проверить.

## Стек

Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async) + Alembic, PostgreSQL 16 + pgvector,
Redis + arq, LangGraph, structlog, pytest, ruff, mypy strict, Docker Compose, GitHub Actions.

## Быстрый старт

```bash
cp .env.example .env          # заполнить ADLEX_DATABASE_URL и ADLEX_LLM_API_KEY
uv sync --all-groups          # окружение и зависимости
make up                       # postgres + redis в docker
make run                      # http://localhost:8000/docs
```

Проверка, что сервис живой:

```bash
curl localhost:8000/healthz   # {"status":"ok"} — процесс жив
curl localhost:8000/readyz    # {"db":"ok","redis":"ok"} — зависимости доступны
```

Всё целиком в контейнерах, включая приложение:

```bash
docker compose up -d --build
```

## Запуск в Kubernetes (k3d)

Локальный кластер: API, миграции отдельным Job, PostgreSQL (StatefulSet) и Redis.
Манифесты — в `k8s/`, раскладка base/overlays под Kustomize.

```bash
k3d cluster create adlex -p "8080:80@loadbalancer" --agents 1
docker build -t adlex:0.1.0 -f docker/Dockerfile .
k3d image import adlex:0.1.0 -c adlex
cp k8s/overlays/dev/secrets.env.example k8s/overlays/dev/secrets.env   # подставить ключ LLM
kubectl apply -k k8s/overlays/dev
kubectl wait --for=condition=complete job/adlex-migrate --timeout=180s
curl localhost:8080/readyz    # {"db":"ok","redis":"ok"}
```

На Windows, если `kubectl` падает по таймауту на `host.docker.internal`:

```bash
kubectl config set-cluster k3d-adlex --server=https://127.0.0.1:$(docker port k3d-adlex-serverlb 6443/tcp | head -1 | cut -d: -f2)
```

## Команды

| Команда | Что делает |
|---|---|
| `make up` / `make down` | поднять / погасить postgres и redis |
| `make migrate` | накатить миграции Alembic на базу |
| `make run` | приложение с автоперезагрузкой |
| `make lint` | ruff check, ruff format --check, mypy strict |
| `make fmt` | автоформатирование и безопасные автоправки |
| `make test` | быстрые тесты (без контейнеров и без обращений к LLM) |

## Структура

```
src/adlex/
  config.py logging.py main.py
  api/       HTTP-контур: роутеры, схемы, зависимости
  db/        модели SQLAlchemy и репозитории
  rag/       парсинг корпуса, чанкинг, эмбеддинги, поиск
  llm/       клиент провайдера и промпты
  agent/     граф LangGraph, узлы, инструменты
  guards/ workers/ observability/
tests/       unit, integration, e2e
corpus/ evals/ scripts/ docker/ mock_api/ k8s/
```

Зависимости слоёв направлены в одну сторону: `api → agent → rag / llm / db`.
База ничего не знает про LLM, LLM — про HTTP.

## Статус

Проект в разработке. Готово: каркас сервиса, конфигурация, структурные логи с `request_id`,
health-эндпоинты, окружение в Docker Compose, CI; схема данных (корпус, диалоги,
наблюдаемость агента) с миграциями Alembic, GIN-индексом по русскому полнотексту
и HNSW-индексом по эмбеддингам; развёртывание в Kubernetes (k3d): пробы, Job с миграциями, Kustomize.
