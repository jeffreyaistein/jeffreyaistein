"""
Jeffrey AIstein - Database Base Configuration
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


# Convert database URL for async SQLAlchemy
# Fly Postgres uses postgres:// but SQLAlchemy needs postgresql+asyncpg://
# Also converts sslmode parameter to asyncpg-compatible ssl parameter
def _get_async_database_url(url: str) -> str:
    """Convert database URL to async-compatible format."""
    # Convert postgres:// to postgresql+asyncpg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # Remove sslmode parameter - asyncpg handles SSL differently
    # For Fly internal connections, SSL is not needed
    if "sslmode=disable" in url:
        url = url.replace("?sslmode=disable", "")
        url = url.replace("&sslmode=disable", "")

    return url


# Create async engine
engine = create_async_engine(
    _get_async_database_url(settings.database_url),
    echo=settings.debug,
    future=True,
)

# Create session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """Dependency for getting database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
