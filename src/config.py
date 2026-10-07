from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "Trợ lý tuyển sinh X"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"

    # LLM
    openai_api_key: str = ""
    model_name: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    # Local MVP. LLM is opt-in so a demo never spends money implicitly.
    answer_mode: Literal["extractive", "llm"] = "extractive"
    staff_username: str = "canbo"
    staff_password: str = "Demo@2026!"
    # Google OAuth is opt-in. A configured allow-list is required so a Google
    # account alone never grants access to the staff dashboard.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://127.0.0.1:8000/api/v1/staff/google/callback"
    google_student_redirect_uri: str = "http://127.0.0.1:8000/api/v1/auth/google/callback"
    google_allowed_emails: str = ""
    google_allowed_email_domains: str = ""
    # Student accounts and SMTP email verification.
    auth_secret: str = ""
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = Field(default="", validation_alias=AliasChoices("SMTP_USER", "SMTP_USERNAME"))
    smtp_password: str = ""
    smtp_from: str = Field(default="", validation_alias=AliasChoices("SMTP_FROM", "SMTP_FROM_EMAIL"))
    smtp_from_name: str = "Trá»£ lÃ½ tuyá»ƒn sinh X"
    smtp_security: Literal["starttls", "ssl"] = "starttls"
    smtp_starttls: bool = Field(default=True, validation_alias=AliasChoices("SMTP_STARTTLS"))
    smtp_timeout: int = Field(default=15, ge=3, le=60)
    public_base_url: str = "http://127.0.0.1:8000"
    verification_code_minutes: int = Field(default=10, ge=5, le=60)
    verification_max_attempts: int = Field(default=5, ge=1, le=10)
    mvp_data_dir: str = "data"
    session_hours: int = Field(default=24, ge=1, le=168)
    secure_cookies: bool = False
    llm_daily_limit: int = Field(default=100, ge=0, le=10000)
    llm_timeout: int = Field(default=15, ge=1, le=20)


@lru_cache
def get_settings() -> Settings:
    return Settings()
