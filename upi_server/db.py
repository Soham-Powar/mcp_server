"""Read-only SQLite access layer for the MCP analytics tools.

Every connection is opened with PRAGMA query_only=ON, and a guard rejects
any statement that is not a plain SELECT/WITH. This is the enforcement
point that keeps the LLM (and the tools themselves) read-only: no INSERT,
UPDATE, DELETE, ALTER, DROP, or arbitrary SQL can run through here.
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from typing import Any, Sequence

# Allow "import shared.config" when run as a standalone MCP process.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import config  # noqa: E402

# Statements we allow. Anything else raises before touching the DB.
_ALLOWED_PREFIX = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|"
    r"detach|pragma|vacuum|reindex)\b",
    re.IGNORECASE,
)


def _connect() -> sqlite3.Connection:
    if not os.path.exists(config.DB_PATH):
        raise FileNotFoundError(
            f"Database not found at {config.DB_PATH}. "
            "Run `python database/seed.py` first."
        )
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON;")
    return conn


def _assert_read_only(sql: str) -> None:
    if not _ALLOWED_PREFIX.match(sql):
        raise ValueError("Only SELECT/WITH queries are permitted.")
    # Strip string literals before scanning for forbidden keywords so a
    # remark like 'update address' in data never trips the guard.
    scrubbed = re.sub(r"'[^']*'", "''", sql)
    if _FORBIDDEN.search(scrubbed):
        raise ValueError("Query contains a forbidden (write) keyword.")


def query(sql: str, params: Sequence[Any] | None = None) -> list[dict]:
    """Run a read-only SELECT and return rows as a list of dicts."""
    _assert_read_only(sql)
    conn = _connect()
    try:
        cur = conn.execute(sql, tuple(params or ()))
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def query_one(sql: str, params: Sequence[Any] | None = None) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None
