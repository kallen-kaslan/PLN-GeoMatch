from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", hide_input_in_errors=True)
    APP_ENV: Literal["development", "production"] = "development"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/pln_geomatch"
    SECRET_KEY: str = ""  # Legacy JWT configuration; opaque sessions do not use it.
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REDIS_URL: str = "redis://localhost:6379/0"
    UPLOAD_STORAGE_DIR: str = str(
        Path(__file__).resolve().parents[1] / "storage" / "uploads"
    )
    ALLOW_SYNC_FALLBACK: bool = False  # Hanya aktif jika eksplisit di-set True di .env (misal untuk dev tanpa Redis)
    AUTH_COOKIE_SECURE: bool = False  # Production requires HTTPS and secure cookies.
    AUTH_IDLE_MINUTES: int = Field(30, ge=5, le=60)
    AUTH_ABSOLUTE_HOURS: int = Field(8, ge=1, le=24)
    AUTH_LOGIN_ACCOUNT_LIMIT: int = Field(5, ge=1, le=20)
    AUTH_LOGIN_IP_LIMIT: int = Field(40, ge=5, le=200)
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    ALLOW_TEST_DATA_TOOLS: bool = False

    @model_validator(mode="after")
    def secure_production(self):
        if "*" in self.CORS_ALLOWED_ORIGINS:
            raise ValueError("CORS harus menggunakan daftar origin eksplisit")
        if self.APP_ENV == "production":
            if not self.AUTH_COOKIE_SECURE or self.ALLOW_TEST_DATA_TOOLS:
                raise ValueError(
                    "Produksi wajib memakai cookie Secure dan menonaktifkan alat data uji"
                )
            if not self.CORS_ALLOWED_ORIGINS or any(
                not origin.startswith("https://")
                for origin in self.CORS_ALLOWED_ORIGINS
            ):
                raise ValueError("Origin produksi wajib memakai HTTPS")
        return self


settings = Settings()
