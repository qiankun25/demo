"""Database connection and session management."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

from app.config import settings

# Create declarative base for models
Base = declarative_base()

# Lazy initialization for async engine
_async_engine = None
_async_session_factory = None


def get_async_engine():
    """Get or create async engine."""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
    return _async_engine


def get_async_session_factory():
    """Get or create async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_factory

# Create sync engine for Celery workers (since Celery doesn't support async)
sync_engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

# Create sync session factory
SessionLocal = sessionmaker(
    sync_engine,
    autocommit=False,
    autoflush=False,
)


async def init_db():
    """Initialize database by creating all tables."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def init_db_sync():
    """Initialize database synchronously (for Celery workers)."""
    Base.metadata.create_all(bind=sync_engine)


async def get_async_session():
    """Dependency for FastAPI to get async database session."""
    session_factory = get_async_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


def get_sync_session():
    """Get sync database session for Celery workers."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
