"""Application settings.

Every value can be overridden through environment variables or a ``.env``
file in the backend directory (see ``.env.example``).  Settings are validated
once at import time so that misconfiguration fails fast instead of surfacing
as a runtime error in the middle of a scan.
"""
from __future__ import annotations

import warnings

from pydantic import AliasChoices, Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The default secret exists only so that a fresh checkout boots for local
# development.  It is rejected outright when ENV=production.
_DEV_JWT_SECRET = "metrologyai_dev_only_jwt_secret_change_me_before_any_deployment"


class Settings(BaseSettings):
    PROJECT_NAME: str = "MetrologyAI API Service"
    VERSION: str = "0.2.0"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"  # development | production

    # JWT Authentication
    JWT_SECRET_KEY: str = _DEV_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12 hours (one field shift)

    # Browser origins allowed to call the API (comma separated).  Localhost on
    # any port is always allowed in development.
    CORS_ORIGINS: str = ""

    # Object Storage Configuration (local | s3)
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_DIR: str = "uploads"
    S3_BUCKET_NAME: str | None = None
    S3_REGION: str | None = "ap-south-1"
    S3_ENDPOINT_URL: str | None = None
    S3_ACCESS_KEY: str | None = None
    S3_SECRET_KEY: str | None = None

    # Evidence file access.  Files are never served from a public static mount;
    # ``/api/v1/files/{key}`` requires either a bearer token or a short-lived
    # signed ``token`` query parameter (used by <img> tags in the dashboard).
    FILE_URL_TTL_SECONDS: int = 60 * 60

    # Upload limits
    MAX_UPLOAD_BYTES: int = 15 * 1024 * 1024

    # Vision engines.  ``paddle`` is the production OCR; ``mock`` returns a fixed
    # synthetic label and is only for tests / UI development.
    OCR_ENGINE: str = "paddle"  # paddle | mock
    SEMANTIC_ENGINE: str = "rules"  # rules | florence2
    DETECTOR_ENGINE: str = "auto"  # auto | yolov8 | geometric
    PIPELINE_MAX_CONCURRENCY: int = 2
    # Tests and one-off scripts set this to avoid touching the database / models at import.
    SKIP_STARTUP_TASKS: bool = False

    # PostgreSQL Configuration
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgrespassword"
    POSTGRES_DB: str = "metrologyai"

    # Explicit override.  ``DATABASE_URL`` is accepted as an alias because that
    # is the conventional name on most hosting platforms.
    SQLALCHEMY_DATABASE_URI: str | None = None
    DATABASE_URL_OVERRIDE: str | None = Field(
        default=None, validation_alias=AliasChoices("DATABASE_URL", "DATABASE_URL_OVERRIDE")
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        if self.SQLALCHEMY_DATABASE_URI:
            return self.SQLALCHEMY_DATABASE_URI
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validate_security(self) -> Settings:
        if self.JWT_SECRET_KEY == _DEV_JWT_SECRET or len(self.JWT_SECRET_KEY) < 32:
            if self.is_production:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a unique value of at least 32 characters when ENV=production"
                )
            warnings.warn(
                "Using the built-in development JWT secret. Set JWT_SECRET_KEY before exposing this API.",
                stacklevel=2,
            )
        if self.OCR_ENGINE not in {"paddle", "mock"}:
            raise ValueError("OCR_ENGINE must be 'paddle' or 'mock'")
        if self.SEMANTIC_ENGINE not in {"rules", "florence2"}:
            raise ValueError("SEMANTIC_ENGINE must be 'rules' or 'florence2'")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
