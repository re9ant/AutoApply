import json
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMProviderType(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    CUSTOM_OPENAI = "custom_openai"
    MOCK = "mock"


class ProviderConfig(BaseModel):
    provider_type: LLMProviderType = LLMProviderType.OPENAI
    api_key: Optional[str] = None
    model: str = "gpt-4o-mini"
    base_url: Optional[str] = None
    temperature: float = 0.1


class BaseLLMProvider(ABC):
    """Abstract base provider for LLMs."""

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    async def extract_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_model: Type[T]
    ) -> T:
        pass

    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        pass


class OpenAICompatibleProvider(BaseLLMProvider):
    """Handles OpenAI, Google Gemini (OpenAI compat), Ollama, and LM Studio."""

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self._client: Optional[AsyncOpenAI] = None
        self._init_client()

    def _init_client(self):
        # Configure base URLs for common providers if not explicitly set
        base_url = self.config.base_url
        if self.config.provider_type == LLMProviderType.OLLAMA and not base_url:
            base_url = "http://localhost:11434/v1"
        elif self.config.provider_type == LLMProviderType.GEMINI:
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
            clean_model = (self.config.model or "").strip()
            if clean_model.startswith("models/"):
                clean_model = clean_model[7:]
            if not clean_model or "gpt-" in clean_model.lower():
                clean_model = "gemini-1.5-flash"
            self.config.model = clean_model

        api_key = self.config.api_key or "dummy-key-for-local"
        if self.config.provider_type in [LLMProviderType.OPENAI, LLMProviderType.GEMINI] and not self.config.api_key:
            self._client = None
            return

        try:
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI-compatible client: {e}")
            self._client = None

    async def extract_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_model: Type[T]
    ) -> T:
        if not self._client:
            raise RuntimeError(f"Client for {self.config.provider_type.value} is not configured or missing API key.")

        try:
            # First attempt native structured outputs
            completion = await self._client.beta.chat.completions.parse(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                response_format=response_model,
                temperature=self.config.temperature
            )
            parsed = completion.choices[0].message.parsed
            if parsed:
                return parsed
        except Exception as e:
            logger.warning(f"Native parse failed on {self.config.provider_type.value}, falling back to json_object mode: {e}")

        # Fallback to json_object format for local LLMs/Ollama
        schema_json = json.dumps(response_model.model_json_schema(), indent=2)
        system_with_schema = (
            f"{system_prompt}\n\n"
            f"You MUST respond with valid JSON strictly adhering to this JSON Schema:\n{schema_json}"
        )

        response = await self._client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=self.config.temperature
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return response_model.model_validate(data)

    async def test_connection(self) -> Dict[str, Any]:
        if not self._client:
            return {
                "success": False,
                "message": f"API key is missing for {self.config.provider_type.value}"
            }
        try:
            response = await self._client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": "Ping"}],
                max_tokens=5
            )
            return {
                "success": True,
                "provider": self.config.provider_type.value,
                "model": self.config.model,
                "message": "Connection successful!",
                "reply": response.choices[0].message.content
            }
        except Exception as e:
            return {
                "success": False,
                "provider": self.config.provider_type.value,
                "model": self.config.model,
                "message": f"Connection failed: {str(e)}"
            }


class MockProvider(BaseLLMProvider):
    """Mock offline provider when no external API key is supplied."""

    async def extract_structured(
        self,
        system_prompt: str,
        user_content: str,
        response_model: Type[T]
    ) -> T:
        raise NotImplementedError("MockProvider does not generate synthetic responses; use heuristic parser.")

    async def test_connection(self) -> Dict[str, Any]:
        return {
            "success": True,
            "provider": "mock",
            "model": "offline-heuristic",
            "message": "Offline heuristic mode active (no external API calls needed)."
        }


class ProviderFactory:
    """Manages available LLM provider instances and active provider selection."""

    _active_config: ProviderConfig = ProviderConfig(
        provider_type=LLMProviderType.OPENAI,
        model="gpt-4o-mini"
    )

    @classmethod
    def get_provider(cls, config: Optional[ProviderConfig] = None) -> BaseLLMProvider:
        cfg = config or cls._active_config

        if cfg.provider_type in [
            LLMProviderType.OPENAI,
            LLMProviderType.GEMINI,
            LLMProviderType.OLLAMA,
            LLMProviderType.CUSTOM_OPENAI
        ]:
            return OpenAICompatibleProvider(cfg)
        return MockProvider(cfg)

    @classmethod
    def set_active_config(cls, config: ProviderConfig) -> None:
        cls._active_config = config

    @classmethod
    def get_active_config(cls) -> ProviderConfig:
        return cls._active_config
