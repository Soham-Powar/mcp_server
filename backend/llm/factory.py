"""Provider factory — selects an LLMProvider from config/env.

The rest of the backend depends only on the LLMProvider interface, so
switching providers is a one-line config change once a provider is
implemented.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared import config  # noqa: E402
from backend.llm.base import LLMProvider  # noqa: E402
from backend.llm.ollama_provider import OllamaProvider  # noqa: E402


def get_provider(name: str | None = None) -> LLMProvider:
    provider = (name or config.LLM_PROVIDER).lower()
    if provider == "ollama":
        return OllamaProvider()
    if provider == "openai":
        from backend.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=os.environ.get("OPENAI_API_KEY"))
    if provider == "anthropic":
        from backend.llm.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    raise ValueError(f"Unknown LLM provider: {provider}")
