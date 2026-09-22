from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from adlex.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """HTTP-клиент поверх ASGI-приложения: без сети, без поднятого сервера.

    Приложение собирается фабрикой, но lifespan намеренно не запускается —
    значит, нет ни движка БД, ни Redis. Всё, что можно проверить здесь,
    не должно зависеть от внешних сервисов.
    """
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
