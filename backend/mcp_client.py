"""Async MCP client that manages MANY FastMCP servers over stdio.

Each configured server is spawned as its own subprocess with its own
long-lived session. Tools from every server are exposed under a namespaced
name ("<server>__<tool>") so names never collide, and call_tool() routes a
namespaced name back to the owning server.

This is what lets one LLM (optionally preceded by a router LLM) work across
multiple domains: UPI today, IMPS / cards / anything tomorrow — by adding a
server entry to config.MCP_SERVERS. No changes needed here or in the frontend.
"""
from __future__ import annotations

import os
import sys
from contextlib import AsyncExitStack
from typing import Any, Iterable, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import config  # noqa: E402

SEP = config.TOOL_NAMESPACE_SEP


class MCPClient:
    def __init__(self, servers: list[dict] | None = None) -> None:
        self._servers = servers if servers is not None else config.MCP_SERVERS
        self._sessions: dict[str, ClientSession] = {}
        self._stack: Optional[AsyncExitStack] = None
        # server name -> list of namespaced tool dicts (cached; catalog static)
        self._tools_by_server: dict[str, list[dict[str, Any]]] = {}

    # --- lifecycle --------------------------------------------------------
    async def connect(self) -> None:
        if self._stack is not None:
            return
        self._stack = AsyncExitStack()
        for spec in self._servers:
            name = spec["name"]
            if SEP in name:
                raise ValueError(
                    f"MCP server name {name!r} must not contain '{SEP}'."
                )
            params = StdioServerParameters(
                command=spec.get("command", "python"),
                args=[spec["script"]],
                env=os.environ.copy(),
            )
            read, write = await self._stack.enter_async_context(
                stdio_client(params)
            )
            session = await self._stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self._sessions[name] = session

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._sessions.clear()
            self._tools_by_server.clear()

    # --- introspection ----------------------------------------------------
    def server_specs(self) -> list[dict]:
        """[{name, description}, ...] — used by the router LLM."""
        return [
            {"name": s["name"], "description": s.get("description", "")}
            for s in self._servers
        ]

    @property
    def server_names(self) -> list[str]:
        return [s["name"] for s in self._servers]

    async def _load_server_tools(self, name: str) -> list[dict[str, Any]]:
        if name in self._tools_by_server:
            return self._tools_by_server[name]
        session = self._sessions[name]
        resp = await session.list_tools()
        tools = [
            {
                # Namespaced so tools from different servers never collide.
                "name": f"{name}{SEP}{t.name}",
                "description": (t.description or "").strip(),
                "parameters": t.inputSchema
                or {"type": "object", "properties": {}},
            }
            for t in resp.tools
        ]
        self._tools_by_server[name] = tools
        return tools

    async def list_tools(
        self, servers: Optional[Iterable[str]] = None
    ) -> list[dict[str, Any]]:
        """Merged, namespaced tool catalog for the given servers (all if None)."""
        names = list(servers) if servers is not None else self.server_names
        merged: list[dict[str, Any]] = []
        for name in names:
            if name in self._sessions:
                merged.extend(await self._load_server_tools(name))
        return merged

    # --- execution --------------------------------------------------------
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Route a namespaced tool name to its server and return result text."""
        if SEP not in name:
            raise ValueError(
                f"Tool name {name!r} is not namespaced as '<server>{SEP}<tool>'."
            )
        server_name, tool_name = name.split(SEP, 1)
        session = self._sessions.get(server_name)
        if session is None:
            raise ValueError(f"Unknown MCP server: {server_name!r}")
        result = await session.call_tool(tool_name, arguments or {})
        parts: list[str] = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
        return "\n".join(parts) if parts else "(no content)"


# Module-level singleton reused across requests.
mcp_client = MCPClient()
