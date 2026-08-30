import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.base import Base
import app.models  # noqa: F401  -- registers every table on Base.metadata


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """A clean in-memory database per test."""
    engine = create_async_engine("sqlite+aiosqlite://")

    # SQLite ignores foreign keys unless asked. Postgres always enforces them,
    # so without this the cascade tests would pass here and fail in production.
    @event.listens_for(engine.sync_engine, "connect")
    def _fk_on(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()
