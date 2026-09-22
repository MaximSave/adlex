from httpx import AsyncClient


async def test_healthz_returns_ok(client: AsyncClient) -> None:
    """Liveness обязан отвечать даже тогда, когда БД и Redis недоступны."""
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_healthz_generates_request_id(client: AsyncClient) -> None:
    """Если клиент не прислал X-Request-ID, его выдаёт middleware."""
    response = await client.get("/healthz")

    assert response.headers["X-Request-ID"]


async def test_healthz_echoes_incoming_request_id(client: AsyncClient) -> None:
    """Свой X-Request-ID возвращается без изменений — по нему сшиваются логи."""
    response = await client.get("/healthz", headers={"X-Request-ID": "req-42"})

    assert response.headers["X-Request-ID"] == "req-42"
