"""Database session management utilities.

Provides engine creation, session factories, and dependency injection helpers
for SQLAlchemy database connections.
"""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Create and cache a SQLAlchemy engine.

    Uses lru_cache to ensure a singleton engine instance is reused
    across the application.

    Returns:
        Engine: SQLAlchemy engine configured with the database URL
            from settings and connection pool health checks enabled.
    """
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


def get_session() -> Session:
    """Create a new database session.

    Returns:
        Session: A new SQLAlchemy session bound to the cached engine.
    """
    engine = get_engine()
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def get_db() -> Generator[Session, None, None]:
    """Yield a database session with automatic cleanup.

    This generator function follows the dependency injection pattern
    used by FastAPI and Dash. It yields a session and ensures proper
    cleanup after use, regardless of whether an exception occurred.

    Yields:
        Session: A SQLAlchemy session for database operations.

    Example:
        # FastAPI dependency injection
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()

        # Manual usage with context manager
        for db in get_db():
            items = db.query(Item).all()
    """
    session = get_session()
    try:
        yield session
    finally:
        session.close()
