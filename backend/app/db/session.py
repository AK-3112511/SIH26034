from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
_session_factory = SessionLocal

def get_session_factory():
    return _session_factory

def set_session_factory(factory):
    global _session_factory
    _session_factory = factory

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session per request."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()

