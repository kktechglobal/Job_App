"""Settings, read from the environment.

`DATABASE_URL` and `SECRET_KEY` come from .env (gitignored), not from a
literal here -- the database password used to sit in tracked source.
Copy .env.example to .env and fill it in.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8",
        case_sensitive=True, extra="ignore",
    )

    PROJECT_NAME: str = "Job Recruitment Platform"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str = "SUPER_SECRET_JWT_KEY_CHANGE_IN_PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    # What "Remember Me" rests on -- the access token stays short-lived.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # Short on purpose: a reset link in an inbox is a standing key to the account.
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30
    FRONTEND_RESET_URL: str = "http://localhost:3000/reset-password"

    # "+asyncpg" is required -- psycopg2 is a sync driver and won't work here.
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_application"

    DB_ECHO: bool = False


settings = Settings()
