from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database.base import Base

DATABASE_URL = "postgresql+asyncpg://postgres:Jombull123@localhost:5432/group_project"
# ---------------------------------------------------------------------------



engine = create_async_engine(DATABASE_URL, echo=True)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


async def init_models():
    """Create any tables that don't already exist."""

    from app import models 
    # Imported for the side effect: defining a model class is what registers its
    # table on Base.metadata, and create_all only creates what's registered.

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_engine():
    """Close the pooled connections."""
    await engine.dispose()
