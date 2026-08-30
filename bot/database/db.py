"""Motor async de SQLAlchemy y utilidades de sesión."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from bot.config import settings
from bot.database.models import Base

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """Devuelve (creando si hace falta) el engine global."""
    global _engine, _session_factory
    if _engine is None:
        url = settings.async_database_url
        _engine = create_async_engine(url, echo=settings.debug, pool_pre_ping=True)
        _session_factory = async_sessionmaker(
            _engine, class_=AsyncSession, expire_on_commit=False
        )
        logger.debug(f"🗄️ Engine creado para {url.split('://', 1)[0]}")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Devuelve la fábrica de sesiones asociada al engine global."""
    get_engine()
    assert _session_factory is not None
    return _session_factory


async def init_db(drop_all: bool = False) -> None:
    """Crea el esquema de la base de datos."""
    engine = get_engine()
    async with engine.begin() as conn:
        if drop_all:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    """Cierra el engine y libera las conexiones."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Context manager transaccional: commit al salir, rollback ante error."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# Alias corto, usado por los handlers.
get_session = session_scope


async def override_engine(url: str) -> None:
    """Reapunta el engine global a otra URL (usado en los tests)."""
    global _engine, _session_factory
    await dispose_db()
    _engine = create_async_engine(url, echo=False)
    _session_factory = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )
