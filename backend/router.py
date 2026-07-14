"""Router LLM: classify a user question to the relevant MCP server(s).

This is the first of the two LLMs. It receives only the server catalog
(names + descriptions) and the latest question, and returns the subset of
servers whose tools should be exposed to the main LLM. Keeping this step
cheap and tool-free means the expensive main model only ever sees the tools
that matter for the question.

Design choices:
- If there is a single server, routing is skipped entirely (returns it).
- The router is asked for STRICT JSON; parsing is lenient and any failure or
  empty/invalid result falls back to "all servers" so we never lose an
  answerable query to a routing mistake.
"""
from __future__ import annotations

import json
import re

from backend.llm.base import LLMProvider

_ROUTER_SYSTEM = (
    "You are a routing classifier. Given a list of available data servers "
    "(each with a name and description) and a user question, choose which "
    "server(s) can answer it. Respond with ONLY a JSON array of server names, "
    'e.g. ["upi"]. Pick the single best server when possible; include multiple '
    "only if the question genuinely spans them. Never invent a name that is "
    "not in the list."
)


def _extract_json_array(text: str) -> list[str] | None:
    """Pull the first JSON array of strings out of a model response."""
    match = re.search(r"\[.*?\]", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        return [str(x) for x in data]
    return None


async def route(
    provider: LLMProvider,
    model: str,
    server_specs: list[dict],
    question: str,
) -> list[str]:
    """Return the list of server names to expose for this question."""
    names = [s["name"] for s in server_specs]

    # Nothing to route.
    if len(server_specs) <= 1:
        return names

    catalog = "\n".join(
        f"- {s['name']}: {s.get('description', '').strip()}" for s in server_specs
    )
    user = (
        f"Available servers:\n{catalog}\n\n"
        f'Question: "{question}"\n\n'
        "Which server(s)? Reply with a JSON array of names only."
    )

    try:
        raw = await provider.complete(
            model,
            [
                {"role": "system", "content": _ROUTER_SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
        )
    except Exception:
        return names  # router unavailable -> expose everything

    picked = _extract_json_array(raw) or []
    # Keep only valid, known names (order-preserving), else fall back to all.
    valid = [n for n in picked if n in names]
    return valid or names


def latest_user_question(messages: list[dict]) -> str:
    """Last user message content — the thing we route on."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "") or ""
    return ""
