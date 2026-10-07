from functools import lru_cache
from typing import Literal

from pydantic import Field
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
    admin_username: str = "admin"
    admin_password: str = "Admin@2026!"
    admin_stale_hours: int = Field(default=24, ge=1, le=720)
    mvp_data_dir: str = "data"
    session_hours: int = Field(default=24, ge=1, le=168)
    secure_cookies: bool = False
    llm_daily_limit: int = Field(default=100, ge=0, le=10000)
    llm_timeout: int = Field(default=15, ge=1, le=20)


@lru_cache
def get_settings() -> Settings:
    return Settings()
