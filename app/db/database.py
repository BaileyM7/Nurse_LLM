import logging
import os
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


def _is_sqlite_corruption(exc: Exception) -> bool:
    """True only for SQLITE_CORRUPT / SQLITE_NOTADB — not permission or I/O errors."""
    orig = getattr(exc, "orig", None)
    if orig is None:
        return False
    msg = str(orig).lower()
    return "database disk image is malformed" in msg or "file is not a database" in msg


def _make_engine(url: str):
    """Create engine; auto-recovers from corrupt SQLite by moving the file aside."""
    try:
        eng = create_engine(url, connect_args=_CONNECT_ARGS)
        # Quick health-check — catches corrupt-file errors at import time.
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng
    except (DatabaseError, OperationalError) as exc:
        # Only attempt recovery for SQLite corruption, not permission/IO errors.
        if not (url.startswith("sqlite:///") and _is_sqlite_corruption(exc)):
            raise
        db_path = Path(url.replace("sqlite:///", "", 1))
        if not (db_path.exists() and os.access(db_path, os.R_OK | os.W_OK)):
            raise
        backup = db_path.with_suffix(f".db.corrupt-{int(time.time())}")
        shutil.move(str(db_path), str(backup))
        logger.warning(
            "DB at %s was corrupt — moved to %s and recreating.",
            db_path,
            backup,
        )
        return create_engine(url, connect_args=_CONNECT_ARGS)


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
