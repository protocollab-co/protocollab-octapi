from __future__ import annotations

from functools import lru_cache
from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict

    _HAS_PYDANTIC_SETTINGS = True
except ImportError:
    from pydantic import BaseSettings  # type: ignore

    SettingsConfigDict = dict  # type: ignore
    _HAS_PYDANTIC_SETTINGS = False


class Settings(BaseSettings):
    if _HAS_PYDANTIC_SETTINGS:
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    if not _HAS_PYDANTIC_SETTINGS:
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "ignore"

    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="qwen2.5-coder:1.5b", alias="OLLAMA_MODEL")
    ollama_timeout_seconds: int = Field(default=60, alias="OLLAMA_TIMEOUT_SECONDS")
    schema_path: str = Field(default="schemas/mws_operation.schema.json", alias="SCHEMA_PATH")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
