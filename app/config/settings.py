"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application controlled by .env file
    app_name: str = "Real Estate Attendance Backend"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False

    # Server controlled by .env file
    host: str = "0.0.0.0"
    port: int = 8000

    # Database controlled by .env file
    database_url: str = (
        "fallback_database_url"
    )

    # JWT Authentication controlled by .env file
    jwt_secret_key: str = "fallback_jwt_secret_key"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # Google OAuth controlled by .env file
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    
    # Google Maps API controlled by .env file
    google_api_key: str = ""
    
    # Frontend URL for OAuth redirects
    frontend_url: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear the settings cache. Useful for testing or when .env changes."""
    get_settings.cache_clear()
