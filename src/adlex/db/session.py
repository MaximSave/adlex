from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from adlex.config import Settings


def create_engine(settings: Settings) -> AsyncEngine:
    """Пул соединений к PostgreSQL.

    Движок создаётся функцией, а не на уровне модуля: на импорте ещё нет event loop,
    такой движок нельзя корректно закрыть и нельзя подменить в тестах. Вызывается
    из lifespan приложения и из фикстур.
    """
    return create_async_engine(
        str(settings.database_url),
        pool_size=10,
        max_overflow=5,
        # Проверка соединения перед выдачей из пула: после разрыва связи с базой
        # первый же запрос иначе падает на «протухшем» соединении.
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Фабрика сессий.

    expire_on_commit=False обязателен в async: иначе после commit все атрибуты
    объектов помечаются протухшими, и следующее обращение к полю вызывает
    неявный SELECT вне корутины — MissingGreenlet.

    autoflush=False убирает скрытые записи в базу перед каждым SELECT:
    момент отправки данных должен быть виден в коде.
    """
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def session_scope(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Транзакция на единицу работы: commit на успехе, rollback на исключении.

    Для кода вне HTTP (скрипты загрузки корпуса, фоновые задачи arq).
    В роутерах ту же логику даёт зависимость `get_session` из api/deps.py.
    """
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
