import logging
from typing import Optional, Type, TypeVar
from pydantic import BaseModel

from app.ai.providers import BaseLLMProvider, LLMProviderType, ProviderConfig, ProviderFactory
from app.config.settings import settings
from app.config.config_store import config_store

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AIClient:
    """Wrapper around Multi-LLM Provider Engine with persistent configuration support."""

    def __init__(self):
        saved = config_store.get_ai_config()

        provider_val = saved.get("provider_type", "openai")
        try:
            provider_enum = LLMProviderType(provider_val)
        except ValueError:
            provider_enum = LLMProviderType.OPENAI

        api_key = saved.get("api_key") or settings.OPENAI_API_KEY
        model = saved.get("model") or settings.OPENAI_MODEL
        base_url = saved.get("base_url") or None
        temperature = saved.get("temperature", settings.OPENAI_TEMPERATURE)

        if provider_enum == LLMProviderType.GEMINI:
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            if model and model.startswith("models/"):
                model = model[7:]
            if not model or model.lower() in ["gemini", "gemini-pro", "models/gemini", "mock", "none"] or "gpt-" in model.lower():
                model = "gemini-1.5-flash"

        if not api_key and provider_enum not in [LLMProviderType.MOCK, LLMProviderType.OLLAMA]:
            provider_enum = LLMProviderType.MOCK

        self.config = ProviderConfig(
            provider_type=provider_enum,
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=temperature
        )
        ProviderFactory.set_active_config(self.config)

    @property
    def is_available(self) -> bool:
        return self.config.provider_type != LLMProviderType.MOCK and (
            bool(self.config.api_key) or self.config.provider_type == LLMProviderType.OLLAMA
        )

    def set_config(self, new_config: ProviderConfig) -> None:
        if new_config.provider_type == LLMProviderType.GEMINI:
            new_config.base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            m = (new_config.model or "").strip()
            if m.startswith("models/"):
                m = m[7:]
            if not m or m.lower() in ["gemini", "gemini-pro", "models/gemini", "mock", "none"] or "gpt-" in m.lower():
                m = "gemini-1.5-flash"
            new_config.model = m

        self.config = new_config
        ProviderFactory.set_active_config(new_config)
        config_store.set_ai_config({
            "provider_type": new_config.provider_type.value,
            "api_key": new_config.api_key or "",
            "model": new_config.model,
            "base_url": new_config.base_url or "",
            "temperature": new_config.temperature
        })

    def get_provider(self) -> BaseLLMProvider:
        return ProviderFactory.get_provider(self.config)

    async def extract_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_model: Type[T]
    ) -> T:
        provider = self.get_provider()
        return await provider.extract_structured(system_prompt, user_content, response_model)

    async def test_connection(self) -> dict:
        provider = self.get_provider()
        return await provider.test_connection()


ai_client = AIClient()
