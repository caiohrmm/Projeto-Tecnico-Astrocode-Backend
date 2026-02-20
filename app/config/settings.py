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
    
    # Gemini API controlled by .env file
    gemini_api_key: str = ""
    
    # Cloudinary controlled by .env file
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    
    # Frontend URL for OAuth redirects (e.g. where to send user after Google login)
    frontend_url: str = "http://localhost:5173"

    # CORS: comma-separated list of allowed origins (e.g. https://meu-app.vercel.app)
    # Env CORS_ORIGINS overrides this. Default includes localhost + frontend em produção (Vercel).
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000,https://frontend-astrocode.vercel.app"

    # SMTP for password reset emails (optional; if not set, link is logged to console)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@example.com"
    smtp_use_tls: bool = True

    def get_cors_origins_list(self) -> list[str]:
        """Return CORS allowed origins (from env + frontend produção sempre incluído)."""
        from_env = [x.strip() for x in self.cors_origins.split(",") if x.strip()]
        production_frontend = "https://frontend-astrocode.vercel.app"
        if production_frontend not in from_env:
            from_env.append(production_frontend)
        return from_env


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


def clear_settings_cache() -> None:
    """Clear the settings cache. Useful for testing or when .env changes."""
    get_settings.cache_clear()
