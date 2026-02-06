"""Database engine and session management."""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings
from app.db.base import Base

settings = get_settings()

# Configure connection arguments for Neon (and other PostgreSQL providers)
connect_args = {}
if "neon.tech" in settings.database_url or "neon" in settings.database_url.lower():
    # Neon-specific SSL configuration
    connect_args = {
        "sslmode": "require",
        "connect_timeout": 10,
    }

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,  # Recycle connections after 1 hour
    pool_timeout=30,  # Timeout for getting connection from pool
    echo=settings.debug,
    connect_args=connect_args,
)

# Add event listener to handle connection errors gracefully
@event.listens_for(engine, "connect")
def set_connection_timeout(dbapi_conn, connection_record):
    """Set connection timeout for PostgreSQL connections."""
    if hasattr(dbapi_conn, "set_session"):
        # Set statement timeout (optional, helps prevent long-running queries)
        with dbapi_conn.cursor() as cursor:
            cursor.execute("SET statement_timeout = '30s'")

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.

    Yields a session and ensures it is properly closed after the request,
    even if an exception occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
