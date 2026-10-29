"""Liveness and readiness probes for the API process and its dependencies."""

import logging
from typing import Any

from fastapi import APIRouter, Response, status
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings

router = APIRouter(tags=["health"])

_check_logger = logging.getLogger(__name__)

_DB_CONNECT_TIMEOUT_SECONDS = 2
_REDIS_CONNECT_TIMEOUT_SECONDS = 1


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe: returns 200 whenever the process can serve requests."""
    return {"status": "ok"}


def _check_database(database_url: str) -> bool:
    """Return True if a trivial query succeeds within the timeout."""
    engine = create_engine(
        database_url,
        connect_args={
            "connect_timeout": _DB_CONNECT_TIMEOUT_SECONDS,
            "application_name": "docintel-ready",
        },
        pool_pre_ping=True,
    )
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        _check_logger.warning("readiness check failed", extra={"check": "database"})
        return False
    finally:
        engine.dispose()


def _check_redis(redis_url: str) -> bool:
    """Return True if PING succeeds within the timeout."""
    client = Redis.from_url(
        redis_url,
        socket_connect_timeout=_REDIS_CONNECT_TIMEOUT_SECONDS,
        socket_timeout=_REDIS_CONNECT_TIMEOUT_SECONDS,
    )
    try:
        return bool(client.ping())
    except RedisError:
        _check_logger.warning("readiness check failed", extra={"check": "redis"})
        return False
    finally:
        client.close()


@router.get("/ready")
async def ready(response: Response) -> dict[str, Any]:
    """Readiness probe: 200 when database and Redis respond, else 503."""
    settings = get_settings()
    checks = {
        "database": _check_database(settings.database_url),
        "redis": _check_redis(settings.redis_url),
    }
    is_ready = all(checks.values())
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if is_ready else "not_ready", "checks": checks}
