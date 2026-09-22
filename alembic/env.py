import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from adlex.config import get_settings

# Импорт пакета моделей обязателен: он наполняет Base.metadata таблицами.
# Без него автогенерация решит, что в схеме ничего нет, и предложит всё удалить.
from adlex.db.models import Base
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Строка подключения берётся из Settings, а не из alembic.ini: одна точка правды,
# и в CI/Docker не нужно держать второй конфиг с паролем.
config.set_main_option("sqlalchemy.url", str(get_settings().database_url))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Режим генерации SQL без подключения к базе (alembic upgrade --sql)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Замечать смену типа колонки и server_default — без этих флагов
        # Alembic такие правки молча пропускает.
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        # NullPool: миграции — короткоживущий процесс, пул соединений ему не нужен.
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
