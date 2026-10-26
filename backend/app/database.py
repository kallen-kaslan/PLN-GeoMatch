import os

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


def ensure_schema_compatibility() -> None:
    """Preserve old records while upgrading the local compatibility schema."""
    from app.master_schema import upgrade_master_catalog
    from app.pdpj_schema import upgrade_pdpj_validation
    from app.correction_schema import upgrade_corrections
    from app.correction_map_schema import upgrade_correction_map
    from app.schema_compatibility import upgrade_foundations

    with engine.begin() as connection:
        upgrade_foundations(connection)
        upgrade_master_catalog(connection)
        upgrade_pdpj_validation(connection)
        upgrade_corrections(connection)
        upgrade_correction_map(connection)


# Coba sambung ke PostgreSQL, jika gagal gunakan SQLite lokal otomatis
DATABASE_URL = settings.DATABASE_URL

try:
    if "postgresql" in DATABASE_URL:
        # Cek apakah koneksi postgres bisa dibuka
        # Coba koneksi cepat
        engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            pass
    else:
        engine = create_engine(DATABASE_URL)
except (SQLAlchemyError, ImportError):
    # Fallback aman ke SQLite lokal untuk development/testing instan
    sqlite_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pln_geomatch.db"
    )
    DATABASE_URL = f"sqlite:///{sqlite_path}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    print(f"[DATABASE] Menggunakan SQLite fallback: {sqlite_path}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Typed declarative base shared by all database models."""


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
