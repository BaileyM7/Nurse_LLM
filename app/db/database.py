import logging
import shutil
import time
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

_DB_URL = settings.database_url
_CONNECT_ARGS = {"check_same_thread": False}


def _make_engine(url: str):
    """Create a SQLAlchemy engine, recovering gracefully from a corrupt SQLite file."""
    try:
        eng = create_engine(url, connect_args=_CONNECT_ARGS)
        # Quick health-check — catches corrupt-file errors at import time.
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except (DatabaseError, OperationalError) as exc:
        if url.startswith("sqlite:///"):
            db_path = Path(url.replace("sqlite:///", "", 1))
            if db_path.exists():
                backup = db_path.with_suffix(f".db.corrupt-{int(time.time())}")
                shutil.move(str(db_path), str(backup))
                logger.warning(
                    "DB at %s was corrupt — moved to %s and recreating.",
                    db_path,
                    backup,
                )
                return create_engine(url, connect_args=_CONNECT_ARGS)
        raise exc


engine = _make_engine(_DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)
