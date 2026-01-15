"""Configuration management for Audio Conversation RAG System.

This module provides centralized configuration using pydantic-settings,
supporting environment variables and .env file loading.
"""

from functools import lru_cache

from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        POSTGRES_HOST: PostgreSQL server hostname.
        POSTGRES_USER: PostgreSQL username.
        POSTGRES_PASSWORD: PostgreSQL password (stored securely).
        POSTGRES_DB: PostgreSQL database name.
        POSTGRES_PORT: PostgreSQL server port.
        VOLUME_PATH: Databricks UC Volumes path for audio files.
        DIARIZATION_ENDPOINT: Databricks model serving endpoint for diarization.
        LLM_ENDPOINT: Databricks model serving endpoint for LLM.
        EMBEDDING_ENDPOINT: Databricks model serving endpoint for embeddings.
        DEBUG: Enable debug mode.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required PostgreSQL settings
    POSTGRES_HOST: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr

    # Optional PostgreSQL settings with defaults
    POSTGRES_DB: str = "audio_rag"
    POSTGRES_PORT: int = 5432

    # Databricks settings
    VOLUME_PATH: str = "/Volumes/main/default/audio-recordings"
    DIARIZATION_ENDPOINT: str = "audio-transcription-diarization-endpoint"
    LLM_ENDPOINT: str = "databricks-claude-sonnet-4-5"
    EMBEDDING_ENDPOINT: str = "databricks-gte-large-en"

    # Application settings
    DEBUG: bool = False

    # Audio processing settings
    ENABLE_AUDIO_CHUNKING: bool = True
    DIARIZATION_TIMEOUT_SECONDS: int = 600  # 10 minutes default

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Construct the full PostgreSQL connection string.

        Returns:
            PostgreSQL connection URL in the format:
            postgresql+psycopg://user:password@host:port/db?sslmode=require
        """
        password = self.POSTGRES_PASSWORD.get_secret_value()
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{password}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            f"?sslmode=require"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings instance.

    Uses lru_cache to ensure only one Settings instance is created,
    implementing a singleton pattern for configuration access.

    Returns:
        The application Settings instance.
    """
    return Settings()
