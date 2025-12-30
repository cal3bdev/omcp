"""LLM provider adapters for the planner."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from omcp.config.models import LLMProvider, LLMSettings
from omcp.utils.errors import PlanGenerationError


class LLMAdapter(ABC):
    """Abstract base class for LLM provider adapters."""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Generate a response from the LLM.

        Args:
            system_prompt: System/instruction prompt
            user_prompt: User message with the actual request

        Returns:
            Generated text response

        Raises:
            PlanGenerationError: If generation fails
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the model name being used."""
        ...


class GeminiAdapter(LLMAdapter):
    """Google Gemini adapter."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        temperature: float = 0.1,
        max_tokens: int = 8000,
    ) -> None:
        """Initialize Gemini adapter.

        Args:
            api_key: Google AI API key
            model: Model name (default: gemini-2.0-flash)
            temperature: Generation temperature
            max_tokens: Maximum output tokens
        """
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client: Any = None

    def _get_client(self) -> Any:
        """Get or create the Gemini client."""
        if self._client is None:
            try:
                import google.generativeai as genai
            except ImportError:
                raise PlanGenerationError(
                    "google-generativeai package not installed",
                    details="Install with: uv pip install google-generativeai",
                )

            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(
                model_name=self._model,
                generation_config={
                    "temperature": self._temperature,
                    "max_output_tokens": self._max_tokens,
                    "response_mime_type": "application/json",
                },
            )
        return self._client

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Generate using Gemini."""
        client = self._get_client()

        # Combine prompts for Gemini (it uses a different conversation format)
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

        try:
            response = await client.generate_content_async(full_prompt)
            return response.text
        except Exception as e:
            raise PlanGenerationError(
                "Gemini generation failed",
                details=str(e),
            )

    @property
    def model_name(self) -> str:
        return self._model


class OpenAIAdapter(LLMAdapter):
    """OpenAI adapter."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_tokens: int = 8000,
    ) -> None:
        """Initialize OpenAI adapter."""
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client: Any = None

    def _get_client(self) -> Any:
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError:
                raise PlanGenerationError(
                    "openai package not installed",
                    details="Install with: uv pip install openai",
                )

            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Generate using OpenAI."""
        client = self._get_client()

        try:
            response = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if content is None:
                raise PlanGenerationError("OpenAI returned empty response")
            return content
        except Exception as e:
            if "PlanGenerationError" in str(type(e)):
                raise
            raise PlanGenerationError(
                "OpenAI generation failed",
                details=str(e),
            )

    @property
    def model_name(self) -> str:
        return self._model


class AnthropicAdapter(LLMAdapter):
    """Anthropic Claude adapter."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.1,
        max_tokens: int = 8000,
    ) -> None:
        """Initialize Anthropic adapter."""
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client: Any = None

    def _get_client(self) -> Any:
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                raise PlanGenerationError(
                    "anthropic package not installed",
                    details="Install with: uv pip install anthropic",
                )

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Generate using Anthropic."""
        client = self._get_client()

        try:
            response = await client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt},
                ],
            )
            # Extract text from response
            content = response.content[0]
            if hasattr(content, "text"):
                return content.text
            raise PlanGenerationError("Anthropic returned unexpected response format")
        except Exception as e:
            if "PlanGenerationError" in str(type(e)):
                raise
            raise PlanGenerationError(
                "Anthropic generation failed",
                details=str(e),
            )

    @property
    def model_name(self) -> str:
        return self._model


def create_llm_adapter(settings: LLMSettings) -> LLMAdapter:
    """Create an LLM adapter from settings.

    Args:
        settings: LLM configuration settings

    Returns:
        Configured LLMAdapter instance

    Raises:
        PlanGenerationError: If provider is unsupported or config is invalid
    """
    if not settings.api_key:
        raise PlanGenerationError(
            "LLM API key not configured",
            details="Set llm.api_key in config or use environment variable",
        )

    if settings.provider == LLMProvider.GEMINI:
        return GeminiAdapter(
            api_key=settings.api_key,
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )
    elif settings.provider == LLMProvider.OPENAI:
        return OpenAIAdapter(
            api_key=settings.api_key,
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )
    elif settings.provider == LLMProvider.ANTHROPIC:
        return AnthropicAdapter(
            api_key=settings.api_key,
            model=settings.model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        )
    else:
        raise PlanGenerationError(
            f"Unsupported LLM provider: {settings.provider}",
            details=f"Supported providers: gemini, openai, anthropic",
        )
