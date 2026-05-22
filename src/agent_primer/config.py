from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    openrouter_api_key: str | None = None
    last_model: str | None = None
    recent_paths: list[str] = Field(default_factory=list)


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".config" / "agent-primer" / "config.json"

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        data = json.loads(self.path.read_text(encoding="utf-8"))
        return AppConfig.model_validate(data)

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        if os.name != "nt":
            self.path.chmod(0o600)

    def get_api_key(self, request_key: str | None = None) -> str | None:
        env_key = os.getenv("OPENROUTER_API_KEY")
        if env_key:
            return env_key
        stored_key = self.load().openrouter_api_key
        return stored_key or request_key
