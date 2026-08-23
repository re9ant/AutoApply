import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from app.config.settings import settings

logger = logging.getLogger(__name__)

SETTINGS_FILE = settings.resolve_path(Path("data/settings.json"))


class PersistentConfig(BaseModel):
    ai: Dict[str, Any] = Field(default_factory=lambda: {
        "provider_type": "openai",
        "model": "gpt-4o-mini",
        "base_url": "",
        "api_key": "",
        "temperature": 0.1
    })
    email: Dict[str, Any] = Field(default_factory=lambda: {
        "email_address": "",
        "app_password": "",
        "display_name": "",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "use_tls": True
    })


class ConfigStore:
    """Manages persistent JSON configuration for AI settings and Gmail settings."""

    def __init__(self, file_path: Path = SETTINGS_FILE):
        self.file_path = file_path
        self._config = self._load()

    def _load(self) -> PersistentConfig:
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return PersistentConfig.model_validate(data)
            except Exception as e:
                logger.error(f"Error reading {self.file_path}: {e}")
        return PersistentConfig()

    def save(self) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self._config.model_dump(), f, indent=2)
            logger.info(f"Saved configuration to {self.file_path}")
        except Exception as e:
            logger.error(f"Failed to write configuration to {self.file_path}: {e}")

    def get_ai_config(self) -> Dict[str, Any]:
        return self._config.ai

    def set_ai_config(self, data: Dict[str, Any]) -> None:
        self._config.ai.update(data)
        self.save()

    def get_email_config(self) -> Dict[str, Any]:
        return self._config.email

    def set_email_config(self, data: Dict[str, Any]) -> None:
        self._config.email.update(data)
        self.save()


config_store = ConfigStore()
