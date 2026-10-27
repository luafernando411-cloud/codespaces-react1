from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Aurora Previdencia API"
    environment: str = "development"
    database_url: str = "sqlite:///./aurora.db"
    redis_url: str = ""
    jwt_secret_key: str = "development-only-change-me-32-characters"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    bank_encryption_key: str = ""
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    upload_dir: str = "./uploads"
    max_upload_bytes: int = 10 * 1024 * 1024
    admin_cpf: str = "52998224725"
    admin_email: str = "admin@example.local"
    admin_password: str = "ChangeMe!2026"
    login_max_attempts: int = 5
    login_lock_minutes: int = 15

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_secret(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT_SECRET_KEY deve ter ao menos 32 caracteres")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
