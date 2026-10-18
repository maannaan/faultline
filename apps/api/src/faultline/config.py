"""Runtime configuration loaded from the environment and the repo `.env`."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    falkordb_host: str = "127.0.0.1"
    falkordb_port: int = 6379
    falkordb_password: str = ""
    falkordb_username: str = ""
    falkordb_ssl: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    app_env: str = "development"
    log_level: str = "INFO"
    auth_keys: str = "dev-key:tenant-synthetic,other-key:tenant-other"
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o-mini"
    policy_version: str = "memory-policy-v1"
    schema_version: str = "1"
    max_note_chars: int = 8000
    web_origin: str = "http://127.0.0.1:3010"

    tenant_by_key: dict[str, str] = Field(default_factory=dict)

    def model_post_init(self, __context: object) -> None:
        parsed: dict[str, str] = {}
        for part in self.auth_keys.split(","):
            item = part.strip()
            if not item or ":" not in item:
                continue
            key, tenant_id = item.split(":", 1)
            key = key.strip()
            tenant_id = tenant_id.strip()
            if key and tenant_id:
                parsed[key] = tenant_id
        object.__setattr__(self, "tenant_by_key", parsed)

    def tenant_for_key(self, key: str) -> str | None:
        return self.tenant_by_key.get(key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
