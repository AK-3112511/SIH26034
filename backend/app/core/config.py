from typing import Optional
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "MetrologyAI API Service"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # JWT Authentication
    JWT_SECRET_KEY: str = "metrologyai_super_secret_jwt_key_for_signing_tokens_minimum_32_chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # Object Storage Configuration (local | s3)
    STORAGE_BACKEND: str = "local"
    STORAGE_LOCAL_DIR: str = "uploads"
    S3_BUCKET_NAME: Optional[str] = None
    S3_REGION: Optional[str] = "ap-south-1"
    S3_ENDPOINT_URL: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    
    # PostgreSQL Configuration
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgrespassword"
    POSTGRES_DB: str = "metrologyai"
    
    # Explicit DATABASE_URL override if provided
    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        if self.SQLALCHEMY_DATABASE_URI:
            return self.SQLALCHEMY_DATABASE_URI
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
