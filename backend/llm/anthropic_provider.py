"""Anthropic provider — stub for future support.

Implements the same LLMProvider interface. Fill in with the Anthropic SDK
(messages API with tools + streaming) to enable. Note Anthropic uses a
`tool_use` / `tool_result` block model rather than `tool` role messages,
so the loop in stream_chat differs slightly from Ollama's.
"""
from __future__ import annotations

from typing import Any, AsyncIterator

from backend.llm.base import LLMProvider, ToolExecutor


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    async def list_models(self) -> list[str]:
        raise NotImplementedError("Anthropic provider not implemented in v1.")

    async def complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
    ) -> str:
        raise NotImplementedError("Anthropic provider not implemented in v1.")

    async def stream_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: ToolExecutor,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        raise NotImplementedError("Anthropic provider not implemented in v1.")
        yield  # pragma: no cover
