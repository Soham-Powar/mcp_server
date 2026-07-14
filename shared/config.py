"""Shared configuration resolved from environment variables.

Imported by both the MCP servers and the FastAPI backend so a single
place defines where the databases live and how the LLM layer behaves.
"""
from __future__ import annotations

import json
import os

from dotenv import load_dotenv

# Load environment variables from a .env file if it exists.
load_dotenv()

# Repo root = parent of this /shared directory.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Databases ------------------------------------------------------------
DB_PATH = os.environ.get(
    "UPI_DB_PATH",
    os.path.join(ROOT, "database", "upi.db"),
)
IMPS_DB_PATH = os.environ.get(
    "IMPS_DB_PATH",
    os.path.join(ROOT, "database", "imps.db"),
)

# --- LLM provider ---------------------------------------------------------
# "ollama" today; "openai" / "anthropic" are wired for the future.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama").lower()

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "qwen3")

# --- MCP servers ----------------------------------------------------------
# The backend can connect to MANY MCP servers. Each entry describes how to
# spawn one over stdio plus a `description` the router LLM uses to decide
# which server a question belongs to.
#
# `name` MUST be unique and MUST NOT contain the "__" separator (it is used
# to namespace tools as "<name>__<tool>"). Override the whole list with the
# MCP_SERVERS env var (a JSON array of {name, command, script, description}).

# Retained for backward compatibility / the default UPI server.
MCP_SERVER_CMD = os.environ.get("MCP_SERVER_CMD", "python")
MCP_SERVER_SCRIPT = os.environ.get(
    "MCP_SERVER_SCRIPT",
    os.path.join(ROOT, "upi_server", "server.py"),
)

TOOL_NAMESPACE_SEP = "__"

_DEFAULT_SERVERS = [
    {
        "name": "upi",
        "command": MCP_SERVER_CMD,
        "script": MCP_SERVER_SCRIPT,
        "description": (
            "UPI transaction analytics. Handles questions about UPI payment "
            "history: spending summaries and totals, category breakdowns, top "
            "merchants, transaction statistics, biggest/failed transactions, "
            "search by merchant or amount, and monthly spending trends."
        ),
    },
    {
        "name": "imps",
        "command": MCP_SERVER_CMD,
        "script": os.path.join(ROOT, "imps_server", "server.py"),
        "description": (
            "IMPS (Immediate Payment Service) bank transfer analytics. Handles "
            "questions about account-to-account IMPS transfers: total amount "
            "transferred, average transfer size, transfers by purpose (rent, "
            "salary, loan repayment, investment) or by channel (mobile/internet "
            "banking, branch, ATM), top beneficiaries, biggest/failed transfers, "
            "search by beneficiary or amount, and monthly transfer trends."
        ),
    },
]


def _load_servers() -> list[dict]:
    raw = os.environ.get("MCP_SERVERS", "").strip()
    if raw:
        try:
            servers = json.loads(raw)
            if isinstance(servers, list) and servers:
                return servers
        except json.JSONDecodeError:
            pass  # fall back to defaults on bad JSON
    return _DEFAULT_SERVERS


MCP_SERVERS = _load_servers()

# --- Router (query -> which MCP server) -----------------------------------
# A small/fast LLM classifies each question to the relevant server(s) so the
# main model only receives that server's tools. Auto-skipped when there is a
# single server (nothing to route). Set ROUTER_ENABLED=false to always expose
# every server's tools to the main model instead.
ROUTER_ENABLED = os.environ.get("ROUTER_ENABLED", "true").lower() == "true"
# Small, fast edge model for classification. Override via ROUTER_MODEL.
ROUTER_MODEL = os.environ.get("ROUTER_MODEL", "gemma4:e2b")

# --- Backend --------------------------------------------------------------
BACKEND_HOST = os.environ.get("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = int(os.environ.get("BACKEND_PORT", "8000"))
CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")
