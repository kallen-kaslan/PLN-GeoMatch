from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/pln_geomatch"
    SECRET_KEY: str = "dev-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REDIS_URL: str = "redis://localhost:6379/0"
    UPLOAD_STORAGE_DIR: str = str(Path(__file__).resolve().parents[1] / "storage" / "uploads")
    ALLOW_SYNC_FALLBACK: bool = False  # Hanya aktif jika eksplisit di-set True di .env (misal untuk dev tanpa Redis)

    class Config:
        env_file = ".env"

settings = Settings()
