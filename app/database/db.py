"""Engine, session factory, and the two lifespan hooks."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database.base import Base

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DB_ECHO)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_models() -> None:
    """Create any tables that don't already exist.

    Convenient for a first run, but it only ever CREATEs -- it never ALTERs, so
    it cannot pick up a column added to an existing table. Alembic is the tool
    for that: `alembic upgrade head`. Once migrations are the source of truth,
    drop this call from the lifespan.
    """
    from app import models  # noqa: F401
    # Imported for the side effect: defining a model class is what registers
    # its table on Base.metadata, and create_all only creates what's registered.

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine() -> None:
    """Close the pooled connections."""
    await engine.dispose()
