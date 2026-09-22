"""Миграции должны накатываться на чистую базу и полностью откатываться.

Откат проверяется не ради красоты: невозвратная миграция — это релиз, который
нельзя отменить. Тест требует поднятых контейнеров, поэтому помечен integration
и не входит в быстрый прогон. База, указанная в ADLEX_DATABASE_URL, очищается.
"""

import asyncio

import pytest
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from adlex.config import get_settings
from alembic import command

pytestmark = pytest.mark.integration

TABLES = {"documents", "chunks", "conversations", "messages", "agent_runs", "tool_calls"}


def table_names() -> set[str]:
    """Имена таблиц через единственный драйвер проекта — asyncpg.

    Тест синхронный (alembic внутри сам делает asyncio.run и в живом event loop
    упал бы), поэтому асинхронная часть запускается отдельным asyncio.run.
    """

    async def fetch() -> set[str]:
        engine = create_async_engine(str(get_settings().database_url))
        try:
            async with engine.connect() as conn:
                # inspect работает с синхронным API, run_sync прокидывает его в поток
                # greenlet-адаптера поверх async-соединения.
                return set(
                    await conn.run_sync(lambda sync_conn: inspect(sync_conn).get_table_names())
                )
        finally:
            await engine.dispose()

    return asyncio.run(fetch())


def test_upgrade_and_downgrade_full_cycle() -> None:
    config = Config("alembic.ini")

    command.downgrade(config, "base")
    command.upgrade(config, "head")
    try:
        assert table_names() >= TABLES

        command.downgrade(config, "base")
        assert not (TABLES & table_names())
    finally:
        # База остаётся в рабочем состоянии, чем бы тест ни кончился.
        command.upgrade(config, "head")
