from fastapi import APIRouter, Request, Response, status
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness: процесс жив. Зависимости здесь не проверяются намеренно."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request, response: Response) -> dict[str, str]:
    """Readiness: готов принимать трафик — значит доступны БД и Redis."""
    checks: dict[str, str] = {}

    try:
        async with request.app.state.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"fail: {type(exc).__name__}"

    try:
        await request.app.state.redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"fail: {type(exc).__name__}"

    if any(value != "ok" for value in checks.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return checks
