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
    DENSE_TEMPLATE_VERSION: Literal["e5-job-profile-v1", "e5-job-profile-v2"] = "e5-job-profile-v2"
    # Job extraction v3: add ESCO skill/knowledge labels (filter O7) as a second dictionary.
    # Off = curated dictionary only, for old-vs-new comparison (DECISIONS.md D038).
    JOB_EXTRACTION_ESCO_VOCABULARY: bool = True
    # Jobs page (D045, D059): retrieval returns the top-N jobs by similarity, shown in pages;
    # coverage explains each job on the current page.
    RECOMMENDATION_TOP_N: int = Field(default=100, ge=1, le=500)
    # Re-embed a profile/job automatically after a committed change (D046). The CLI stays for bulk runs.
    AUTO_REINDEX: bool = True
    # Build job representations for the retrieval freshness check in a background thread
    # at startup, so the first Jobs page after a restart is not slow (D059).
    WARM_JOB_CACHE_ON_STARTUP: bool = True

    # Live job import (D052-D056). Lists accept "a,b" or a JSON array.
    LIVE_JOB_SOURCES: str = "arbeitnow,greenhouse"
    # Greenhouse job-board tokens, verified 2026-11-21 to return EU/remote English postings.
    GREENHOUSE_BOARDS: str = (
        "gitlab,elastic,grafanalabs,canonical,datadog,mongodb,twilio,celonis,contentful,commercetools,"
        "stripe,adyen,sumup,n26,monzo,tide,raisin,hellofresh,wolt,intercom"
    )
    ARBEITNOW_MAX_PAGES: int = Field(default=10, ge=1, le=100)
    # Keep only postings located in the EU/EEA, UK, Switzerland or remote without another region.
    LIVE_JOBS_EUROPE_OR_REMOTE_ONLY: bool = True
    LIVE_JOBS_ENGLISH_ONLY: bool = True
    LIVE_JOBS_MAX_ACTIVE: int = Field(default=1500, ge=1)
    # No source above this share of LIVE_JOBS_MAX_ACTIVE (D058); 1.0 switches the limit off.
    LIVE_JOBS_MAX_SOURCE_SHARE: float = Field(default=0.7, gt=0, le=1)
    LIVE_JOBS_ARCHIVE_AFTER_DAYS: int = Field(default=14, ge=1)
    JOB_SOURCE_MIN_INTERVAL_SECONDS: float = Field(default=1.5, ge=0)
    JOB_SOURCE_USER_AGENT: str = "skillgap-job-import/0.1"
    # Jobs page scope (D056): evaluation jobs are not shown to candidates unless enabled.
    CANDIDATE_VIEW_INCLUDES_EVALUATION_JOBS: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    @staticmethod
    def _as_list(value: str) -> list[str]:
        if value.strip().startswith("["):
            return [str(item).strip() for item in json.loads(value) if str(item).strip()]
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def live_job_sources(self) -> list[str]:
        return self._as_list(self.LIVE_JOB_SOURCES)

    @property
    def greenhouse_boards(self) -> list[str]:
        return self._as_list(self.GREENHOUSE_BOARDS)

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
