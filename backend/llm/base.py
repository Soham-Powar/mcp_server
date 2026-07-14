"""Model-agnostic LLM provider interface.

Adding OpenAI or Anthropic later means implementing this one interface —
the backend, MCP loop and frontend stay unchanged.
"""
from __future__ import annotations

import abc
from typing import Any, AsyncIterator, Awaitable, Callable

# Executes an MCP tool: (name, arguments) -> result text.
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[str]]


class LLMProvider(abc.ABC):
    """Contract every provider must satisfy."""

    name: str = "base"

    @abc.abstractmethod
    async def list_models(self) -> list[str]:
        """Return the model names installed/available for this provider."""

    @abc.abstractmethod
    async def complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
    ) -> str:
        """Single-shot, non-streaming completion with NO tools.

        Used by the router LLM to classify a query. Kept separate from
        stream_chat so routing stays cheap and deterministic.
        """

    @abc.abstractmethod
    def stream_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: ToolExecutor,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Run the full chat + tool-calling loop and yield answer text.

        Implementations should: send messages + tools to the model,
        execute any requested tools via `tool_executor`, feed results back,
        then stream the final assistant answer as text chunks.
        """
        raise NotImplementedError
