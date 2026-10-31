"""Application configuration and settings."""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime application settings for NetCoop AI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "NetCoop AI"
    version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # Server binding
    host: str = "127.0.0.1"
    port: int = 8000

    # Persistence
    database_url: str = "sqlite:///./netcoop.db"

    # Optional LLM integration (Gemini)
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-1.5-flash"

    # Orchestrator parameters
    max_inquiry_iterations: int = 3
    agent_timeout_seconds: float = 5.0

    # Remediation safety
    remediation_simulated_only: bool = True


settings = Settings()
