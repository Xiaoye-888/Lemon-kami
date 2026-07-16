from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and local .env files."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    DEBUG: bool = False

    DATABASE_URL: str = "mysql+pymysql://lemon_user:lemon_password_123@localhost:3306/lemon_kami"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENABLE_API_DOCS: bool = False

    TIMESTAMP_TOLERANCE: int = 60
    NONCE_TTL: int = 60
    RATE_LIMIT_MAX: int = 100
    RATE_LIMIT_WINDOW: int = 60
    CORS_ALLOWED_ORIGINS: str = ""

    LOGIN_AES_KEY: Optional[str] = None
    BOOTSTRAP_ADMIN_PASSWORD: Optional[str] = None


settings = Settings()
