import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from redis.asyncio import Redis

from adlex.api.routers import health
from adlex.config import get_settings
from adlex.db.session import create_engine, create_session_factory
from adlex.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.env)

    app.state.settings = settings
    app.state.engine = create_engine(settings)
    app.state.session_factory = create_session_factory(app.state.engine)
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)

    structlog.get_logger().info("app_started", env=settings.env, model=settings.model_main)
    yield

    await app.state.redis.aclose()
    await app.state.engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(title="AdLex", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def add_request_id(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    app.include_router(health.router)
    return app
