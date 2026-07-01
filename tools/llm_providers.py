"""
Multi-Provider LLM Abstraction Layer

Auto-detects available API keys and routes requests to
the appropriate LLM provider (Anthropic, OpenAI, NVIDIA, etc.).
"""

import os
from typing import Optional


class LLMProvider:
    name: str
    api_key_env: str
    default_model: str
    base_url: Optional[str] = None

    def call(self, prompt: str, api_key: str, model: str, max_tokens: int,
             temperature: float, system: Optional[str], timeout_seconds: int) -> str:
        raise NotImplementedError


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    api_key_env = "ANTHROPIC_API_KEY"
    default_model = "claude-sonnet-4-20250514"

    def call(self, prompt: str, api_key: str, model: str, max_tokens: int,
             temperature: float, system: Optional[str], timeout_seconds: int) -> str:
        import anthropic

        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")

        client = anthropic.Anthropic(api_key=api_key, timeout=timeout_seconds)

        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        try:
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except anthropic.APITimeoutError:
            raise RuntimeError(f"Anthropic API timed out after {timeout_seconds}s")
        except anthropic.APIStatusError as e:
            raise RuntimeError(f"Anthropic API error {e.status_code}: {e.message}")
        except Exception as e:
            raise RuntimeError(f"Anthropic API call failed: {e}")


class OpenAICompatibleProvider(LLMProvider):
    """
    Generic provider for any OpenAI-compatible API (OpenAI, NVIDIA, Together, Groq, etc.).

    Subclasses just set name, api_key_env, default_model, and base_url.
    """

    def call(self, prompt: str, api_key: str, model: str, max_tokens: int,
             temperature: float, system: Optional[str], timeout_seconds: int) -> str:
        from openai import OpenAI

        if not api_key:
            raise RuntimeError(f"{self.api_key_env} is not set")

        client = OpenAI(
            api_key=api_key,
            base_url=self.base_url,
            timeout=timeout_seconds,
        )

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise RuntimeError(f"{self.name} API call failed: {e}")


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"
    api_key_env = "OPENAI_API_KEY"
    default_model = "gpt-4o"
    base_url = None


class NVIDIAProvider(OpenAICompatibleProvider):
    name = "nvidia"
    api_key_env = "NVIDIA_API_KEY"
    default_model = "meta/llama-3.1-8b-instruct"
    base_url = "https://integrate.api.nvidia.com/v1"


PROVIDER_REGISTRY: dict[str, LLMProvider] = {
    "anthropic": AnthropicProvider(),
    "openai": OpenAIProvider(),
    "nvidia": NVIDIAProvider(),
}


def detect_available_providers() -> list[str]:
    """Return list of provider names whose API keys are set in environment."""
    available = []
    for name, provider in PROVIDER_REGISTRY.items():
        if os.getenv(provider.api_key_env):
            available.append(name)
    return available


def get_llm(provider_name: Optional[str] = None) -> tuple[LLMProvider, str]:
    """
    Resolve the best available LLM provider.

    Args:
        provider_name: Preferred provider name, or None for auto-detect.

    Returns:
        (provider_instance, api_key)

    Raises:
        RuntimeError: If no provider is available.
    """
    from config.settings import settings

    provider_name = provider_name or settings.LLM_PROVIDER

    if provider_name == "auto" or not provider_name:
        available = detect_available_providers()
        if not available:
            raise RuntimeError(
                "No LLM provider available. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, "
                "or NVIDIA_API_KEY in .env"
            )
        provider_name = available[0]

    provider = PROVIDER_REGISTRY.get(provider_name)
    if not provider:
        raise RuntimeError(f"Unknown LLM provider: {provider_name}. Available: {list(PROVIDER_REGISTRY)}")

    api_key = os.getenv(provider.api_key_env, "")
    if not api_key:
        raise RuntimeError(
            f"{provider.api_key_env} is not set. Cannot use {provider_name} provider."
        )

    return provider, api_key


def call_llm(
    prompt: str,
    provider_name: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    system: Optional[str] = None,
    timeout_seconds: int = 120,
) -> str:
    """
    Unified LLM call that auto-selects the best available provider.

    Args:
        prompt: The user message prompt
        provider_name: "anthropic", "openai", "nvidia", or None for auto-detect
        model: Model override (uses provider default if not specified)
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature
        system: Optional system prompt
        timeout_seconds: Request timeout

    Returns:
        Response text from the LLM

    Raises:
        RuntimeError: If no provider is available or the API call fails
    """
    from config.settings import settings

    provider, api_key = get_llm(provider_name)

    resolved_model = model or getattr(settings, f"{provider.name.upper()}_MODEL", None) or provider.default_model
    resolved_max_tokens = max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS
    resolved_temperature = temperature if temperature is not None else settings.LLM_TEMPERATURE

    return provider.call(
        prompt=prompt,
        api_key=api_key,
        model=resolved_model,
        max_tokens=resolved_max_tokens,
        temperature=resolved_temperature,
        system=system,
        timeout_seconds=timeout_seconds,
    )
