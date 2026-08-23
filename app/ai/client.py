import logging
from typing import Optional, Type, TypeVar
from pydantic import BaseModel

from app.ai.providers import BaseLLMProvider, LLMProviderType, ProviderConfig, ProviderFactory
from app.config.settings import settings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class AIClient:
    """Wrapper around Multi-LLM Provider Engine."""

    def __init__(self):
        # Initialize default config from settings
        default_provider = LLMProviderType.OPENAI if settings.OPENAI_API_KEY else LLMProviderType.MOCK
        self.config = ProviderConfig(
            provider_type=default_provider,
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
            temperature=settings.OPENAI_TEMPERATURE
        )
        ProviderFactory.set_active_config(self.config)

    @property
    def is_available(self) -> bool:
        return self.config.provider_type != LLMProviderType.MOCK and (
            bool(self.config.api_key) or self.config.provider_type == LLMProviderType.OLLAMA
        )

    def set_config(self, new_config: ProviderConfig) -> None:
        self.config = new_config
        ProviderFactory.set_active_config(new_config)

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
