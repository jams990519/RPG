"""Fixtures compartidas por los tests."""
from __future__ import annotations

import random
from typing import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import db as db_module
from bot.database.models import User


@pytest.fixture
def rng() -> random.Random:
    """Generador determinista para que los tests no dependan del azar."""
    return random.Random(1234)


@pytest_asyncio.fixture
async def session(tmp_path) -> AsyncIterator[AsyncSession]:
    """Sesión contra una base SQLite temporal, recreada en cada test."""
    url = f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    await db_module.override_engine(url)
    await db_module.init_db(drop_all=True)
    async with db_module.session_scope() as db_session:
        yield db_session
    await db_module.dispose_db()


@pytest_asyncio.fixture
async def player(session: AsyncSession) -> User:
    """Un jugador con saldo para apostar."""
    user = User(id=1001, username="tester", first_name="Test", coins=1000)
    session.add(user)
    await session.flush()
    return user
