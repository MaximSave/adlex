from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Сессия и транзакция на один HTTP-запрос.

    Фабрика берётся из app.state, куда её положил lifespan, — роутеры не знают
    ни про строку подключения, ни про момент создания пула. В тестах достаточно
    подменить app.state.session_factory.
    """
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Чтобы в роутерах писать `session: SessionDep`, а не тащить Depends в каждую сигнатуру.
SessionDep = Annotated[AsyncSession, Depends(get_session)]
