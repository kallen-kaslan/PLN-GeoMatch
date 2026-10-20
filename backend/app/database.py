from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from .config import settings


def ensure_schema_compatibility() -> None:
    """Add columns introduced after an existing local database was created."""
    inspector = inspect(engine)
    if "master_sisa_records" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("master_sisa_records")}
    if "jenis_layanan" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE master_sisa_records "
                    "ADD COLUMN jenis_layanan VARCHAR DEFAULT 'PASCABAYAR'"
                )
            )
        print("[DATABASE] Added missing column master_sisa_records.jenis_layanan")

# Coba sambung ke PostgreSQL, jika gagal gunakan SQLite lokal otomatis
DATABASE_URL = settings.DATABASE_URL

try:
    if "postgresql" in DATABASE_URL:
        # Cek apakah koneksi postgres bisa dibuka
        import psycopg2
        # Coba koneksi cepat
        engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 2})
        with engine.connect() as conn:
            pass
    else:
        engine = create_engine(DATABASE_URL)
except Exception:
    # Fallback aman ke SQLite lokal untuk development/testing instan
    sqlite_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pln_geomatch.db")
    DATABASE_URL = f"sqlite:///{sqlite_path}"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    print(f"[DATABASE] Menggunakan SQLite fallback: {sqlite_path}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
