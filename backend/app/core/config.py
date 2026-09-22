from functools import lru_cache
import json
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Skill Gap Job Matching System"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    DEBUG: bool = False

    DATABASE_URL: str = Field(
        default="postgresql+psycopg://skillgap:skillgap@db:5432/skillgap"
    )
    TEST_DATABASE_URL: str = "sqlite+pysqlite:///:memory:"

    SECRET_KEY: str = Field(default="change-me-in-production", min_length=16)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_HASH_SCHEME: str = "bcrypt"

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:8080"

    DEFAULT_CANDIDATE_ROLE: str = "candidate"
    ADMIN_ROLE: str = "admin"
    RESEARCHER_ROLE: str = "researcher"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    @property
    def cors_origins(self) -> list[str]:
        if self.CORS_ORIGINS.strip().startswith("["):
            parsed_origins = json.loads(self.CORS_ORIGINS)
            return [str(origin).strip() for origin in parsed_origins if str(origin).strip()]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
