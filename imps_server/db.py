"""Read-only SQLite access layer for the IMPS analytics tools.

Identical safety model to upi_server/db.py: every connection uses
PRAGMA query_only=ON and a guard rejects any non-SELECT statement. Only the
database path differs (config.IMPS_DB_PATH).
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from typing import Any, Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import config  # noqa: E402

_ALLOWED_PREFIX = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)
_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|"
    r"detach|pragma|vacuum|reindex)\b",
    re.IGNORECASE,
)


def _connect() -> sqlite3.Connection:
    if not os.path.exists(config.IMPS_DB_PATH):
        raise FileNotFoundError(
            f"IMPS database not found at {config.IMPS_DB_PATH}. "
            "Run `python database/imps_seed.py` first."
        )
    conn = sqlite3.connect(config.IMPS_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON;")
    return conn


def _assert_read_only(sql: str) -> None:
    if not _ALLOWED_PREFIX.match(sql):
        raise ValueError("Only SELECT/WITH queries are permitted.")
    scrubbed = re.sub(r"'[^']*'", "''", sql)
    if _FORBIDDEN.search(scrubbed):
        raise ValueError("Query contains a forbidden (write) keyword.")


def query(sql: str, params: Sequence[Any] | None = None) -> list[dict]:
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
