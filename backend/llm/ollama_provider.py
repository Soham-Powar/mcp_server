"""Ollama provider: model discovery + streaming chat with MCP tool calls.

Tool-calling loop:
  1. POST /api/chat (non-streamed) with the tool list.
  2. If the model returns tool_calls, execute each via the MCP tool
     executor, append the results as `tool` messages, and repeat.
  3. Once the model stops requesting tools, stream the final answer.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, AsyncIterator

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared import config  # noqa: E402
from backend.llm.base import LLMProvider, ToolExecutor  # noqa: E402

MAX_TOOL_ROUNDS = 6


def _to_ollama_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in tools
    ]


def _get_sources_header(used_servers: set[str]) -> str:
    server_titles = {
        "upi": "UPI Analytics",
        "imps": "IMPS Transfers"
    }
    names = [server_titles.get(s, s.upper()) for s in sorted(used_servers)]
    return f"**Data Source:** {', '.join(names)}\n\n"


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, host: str | None = None) -> None:
        self.host = (host or config.OLLAMA_HOST).rstrip("/")

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{self.host}/api/tags")
            resp.raise_for_status()
            data = resp.json()
        # Strip the ":latest" tag suffix for cleaner display.
        return [m["name"].split(":")[0] if m["name"].endswith(":latest")
                else m["name"] for m in data.get("models", [])]

    async def complete(
        self,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float = 0.0,
    ) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{self.host}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        return (data.get("message") or {}).get("content", "") or ""

    async def _chat_once(
        self,
        client: httpx.AsyncClient,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
    ) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "options": {"temperature": temperature},
        }
        resp = await client.post(f"{self.host}/api/chat", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def stream_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor: ToolExecutor,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        ollama_tools = _to_ollama_tools(tools)
        convo = list(messages)
        used_servers = set()

        async with httpx.AsyncClient(timeout=None) as client:
            # --- Tool-resolution rounds (non-streamed) --------------------
            for _ in range(MAX_TOOL_ROUNDS):
                data = await self._chat_once(
                    client, model, convo, ollama_tools, temperature
                )
                msg = data.get("message", {}) or {}
                tool_calls = msg.get("tool_calls") or []
                if not tool_calls:
                    content = msg.get("content", "")
                    if content:
                        if used_servers:
                            content = _get_sources_header(used_servers) + content
                        yield content
                        return
                    break

                convo.append(msg)
                for call in tool_calls:
                    fn = call.get("function", {})
                    tname = fn.get("name", "")
                    if config.TOOL_NAMESPACE_SEP in tname:
                        srv = tname.split(config.TOOL_NAMESPACE_SEP, 1)[0]
                        used_servers.add(srv)

                    args = fn.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except json.JSONDecodeError:
                            args = {}
                    try:
                        result = await tool_executor(tname, args)
                    except Exception as exc:  # surface tool errors to the model
                        result = f"ERROR calling {tname}: {exc}"
                    convo.append({"role": "tool", "name": tname, "content": result})

            # --- Final streamed answer -----------------------------------
            if used_servers:
                yield _get_sources_header(used_servers)

            payload = {
                "model": model,
                "messages": convo,
                "stream": True,
                "options": {"temperature": temperature},
            }
            async with client.stream(
                "POST", f"{self.host}/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    piece = (chunk.get("message") or {}).get("content", "")
                    if piece:
                        yield piece
                    if chunk.get("done"):
                        break
