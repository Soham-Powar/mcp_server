"""OpenAI provider — stub for future support.

Implements the same LLMProvider interface as Ollama. Fill in the two
methods with the OpenAI SDK (chat.completions with tools + streaming) to
enable. Left unimplemented on purpose so v1 stays local-only.
"""
from __future__ import annotations

from typing import Any, AsyncIterator

from backend.llm.base import LLMProvider, ToolExecutor


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    async def list_models(self) -> list[str]:
        raise NotImplementedError("OpenAI provider not implemented in v1.")

    async def complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
    ) -> str:
        raise NotImplementedError("OpenAI provider not implemented in v1.")

    async def stream_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: ToolExecutor,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        raise NotImplementedError("OpenAI provider not implemented in v1.")
        yield  # pragma: no cover  (marks this an async generator)
