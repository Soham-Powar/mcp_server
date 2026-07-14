"""FastMCP server exposing business-level IMPS analytics tools.

Mirrors the UPI server's design (typed, read-only, no SQL exposed to the LLM)
but for the account-to-account IMPS transfer model: beneficiaries, channels
and purposes instead of merchants and categories.

Run standalone (stdio transport):
    python imps_server/server.py
"""
from __future__ import annotations

import os
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from imps_server import db  # noqa: E402

mcp = FastMCP("imps-analytics")


def _date_clause(start_date: Optional[str], end_date: Optional[str]):
    """(sql_fragment, params) for an inclusive [start, end] date range."""
    clauses, params = [], []
    if start_date:
        clauses.append("timestamp >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("timestamp < datetime(?, '+1 day')")
        params.append(end_date)
    return clauses, params


# Whitelisted sort expressions. `sort_by`/`order` become SQL keywords, so they
# are NEVER interpolated from raw input — only resolved through these maps.
_SORT_EXPR = {
    "total": "SUM(amount)",
    "count": "COUNT(*)",
    "max_amount": "MAX(amount)",
    "avg": "AVG(amount)",
}

# Dimensions the generalized breakdown can group by -> real column.
_DIMENSIONS = {
    "purpose": "purpose",
    "channel": "channel",
    "beneficiary": "beneficiary_name",
    "payee": "beneficiary_name",
    "mode": "transfer_mode",
    "transfer_mode": "transfer_mode",
    "bank": "beneficiary_bank",
}


def _order_by(sort_by: Optional[str], order: Optional[str]) -> str:
    expr = _SORT_EXPR.get((sort_by or "total").lower(), _SORT_EXPR["total"])
    direction = "ASC" if (order or "desc").lower() == "asc" else "DESC"
    return f"{expr} {direction}"


@mcp.tool()
def get_schema() -> dict:
    """Return the IMPS transfers table schema: columns, plus the distinct
    channels, statuses, purposes and transfer modes available, and the date
    range covered. Call this first when unsure what IMPS data exists."""
    cols = db.query("SELECT name, type FROM pragma_table_info('transfers')")
    channels = [r["channel"] for r in db.query(
        "SELECT DISTINCT channel FROM transfers WHERE channel IS NOT NULL ORDER BY 1")]
    statuses = [r["status"] for r in db.query(
        "SELECT DISTINCT status FROM transfers ORDER BY 1")]
    purposes = [r["purpose"] for r in db.query(
        "SELECT DISTINCT purpose FROM transfers WHERE purpose IS NOT NULL ORDER BY 1")]
    modes = [r["transfer_mode"] for r in db.query(
        "SELECT DISTINCT transfer_mode FROM transfers ORDER BY 1")]
    rng = db.query_one(
        "SELECT MIN(timestamp) AS min_ts, MAX(timestamp) AS max_ts, "
        "COUNT(*) AS total FROM transfers")
    return {
        "table": "transfers",
        "columns": cols,
        "channels": channels,
        "statuses": statuses,
        "purposes": purposes,
        "transfer_modes": modes,
        "date_range": {"start": rng["min_ts"], "end": rng["max_ts"]},
        "row_count": rng["total"],
    }


@mcp.tool()
def get_transfers(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    status: Optional[str] = None,
    channel: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """List individual IMPS transfers with optional filters. Dates are
    'YYYY-MM-DD' and inclusive. Returns newest first. Use for 'show IMPS
    transfers in June' or 'failed IMPS transfers'."""
    clauses, params = _date_clause(start_date, end_date)
    if status:
        clauses.append("status = ?")
        params.append(status)
    if channel:
        clauses.append("channel = ?")
        params.append(channel)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    limit = max(1, min(int(limit), 1000))
    return db.query(
        "SELECT transaction_id, timestamp, beneficiary_name, beneficiary_account, "
        "beneficiary_bank, amount, transfer_mode, channel, status, purpose, "
        "rrn, remarks FROM transfers "
        f"{where} ORDER BY timestamp DESC LIMIT ?",
        [*params, limit],
    )


@mcp.tool()
def get_transfer_summary(start_date: str, end_date: str) -> dict:
    """Total amount transferred, transfer count, average transfer size and
    success rate over a date range (inclusive, 'YYYY-MM-DD'). Amount counts
    successful transfers only. Answers 'how much was transferred via IMPS last
    month?' and 'what is the average IMPS transaction amount this month?'."""
    clauses, params = _date_clause(start_date, end_date)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    row = db.query_one(
        "SELECT "
        "COALESCE(SUM(CASE WHEN status='SUCCESS' THEN amount END), 0) AS total_transferred, "
        "COUNT(*) AS total_transfers, "
        "SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END) AS successful, "
        "SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) AS failed, "
        "COALESCE(AVG(CASE WHEN status='SUCCESS' THEN amount END), 0) AS avg_transfer "
        f"FROM transfers {where}",
        params,
    )
    total = row["total_transfers"] or 0
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_transferred": round(row["total_transferred"], 2),
        "total_transfers": total,
        "successful": row["successful"],
        "failed": row["failed"],
        "avg_transfer": round(row["avg_transfer"], 2),
        "success_rate": round((row["successful"] / total) * 100, 1) if total else 0,
    }


@mcp.tool()
def get_purpose_breakdown(start_date: str, end_date: str) -> list[dict]:
    """Amount transferred grouped by purpose (Rent, Salary, Loan Repayment,
    ...) over a date range, sorted by total descending. Successful transfers
    only. Answers 'how much went to rent via IMPS?'."""
    clauses, params = _date_clause(start_date, end_date)
    clauses += ["status = 'SUCCESS'"]
    where = "WHERE " + " AND ".join(clauses)
    return db.query(
        "SELECT purpose, ROUND(SUM(amount), 2) AS total, COUNT(*) AS count, "
        "ROUND(AVG(amount), 2) AS avg_amount "
        f"FROM transfers {where} GROUP BY purpose ORDER BY total DESC",
        params,
    )


@mcp.tool()
def get_channel_breakdown(start_date: str, end_date: str) -> list[dict]:
    """Transfers grouped by channel (Mobile Banking, Internet Banking, Branch,
    ATM, USSD) over a date range, by total amount descending. Successful
    transfers only. Answers 'which channel is used most for IMPS?'."""
    clauses, params = _date_clause(start_date, end_date)
    clauses += ["status = 'SUCCESS'"]
    where = "WHERE " + " AND ".join(clauses)
    return db.query(
        "SELECT channel, ROUND(SUM(amount), 2) AS total, COUNT(*) AS count "
        f"FROM transfers {where} GROUP BY channel ORDER BY total DESC",
        params,
    )


@mcp.tool()
def get_top_beneficiaries(
    start_date: str,
    end_date: str,
    limit: int = 10,
    sort_by: str = "total",
    order: str = "desc",
) -> list[dict]:
    """Rank beneficiaries (payees) over a date range. Generalized ranking:
    `limit=1` returns the single top beneficiary, `limit=10` the top 10.
    `sort_by` is one of 'total' (summed amount, default), 'count' (number of
    transfers), 'max_amount' (largest single transfer) or 'avg' (average
    transfer). `order` is 'desc' (default) or 'asc'. Successful transfers only.
    Answers 'who received the most', 'my most frequent beneficiary',
    'largest single transfer recipient', 'smallest beneficiary'."""
    clauses, params = _date_clause(start_date, end_date)
    clauses += ["status = 'SUCCESS'"]
    where = "WHERE " + " AND ".join(clauses)
    limit = max(1, min(int(limit), 100))
    return db.query(
        "SELECT beneficiary_name, beneficiary_account, beneficiary_bank, "
        "ROUND(SUM(amount), 2) AS total, COUNT(*) AS count, "
        "ROUND(MAX(amount), 2) AS max_amount, ROUND(AVG(amount), 2) AS avg_amount "
        f"FROM transfers {where} "
        "GROUP BY beneficiary_name, beneficiary_account "
        f"ORDER BY {_order_by(sort_by, order)} LIMIT ?",
        [*params, limit],
    )


@mcp.tool()
def get_transfer_stats(start_date: str, end_date: str) -> dict:
    """Descriptive stats over a date range: min / max / average amount, the
    largest single transfer, the busiest channel and the most common purpose.
    Answers 'what was the biggest IMPS transfer?'."""
    clauses, params = _date_clause(start_date, end_date)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    base = db.query_one(
        "SELECT COUNT(*) AS count, ROUND(MIN(amount),2) AS min_amount, "
        "ROUND(MAX(amount),2) AS max_amount, ROUND(AVG(amount),2) AS avg_amount, "
        "ROUND(SUM(amount),2) AS total_amount "
        f"FROM transfers {where}", params)
    biggest = db.query_one(
        "SELECT transaction_id, timestamp, beneficiary_name, amount, purpose "
        f"FROM transfers {where} ORDER BY amount DESC LIMIT 1", params)
    top_channel = db.query_one(
        "SELECT channel, COUNT(*) AS count "
        f"FROM transfers {where} GROUP BY channel ORDER BY count DESC LIMIT 1", params)
    top_purpose = db.query_one(
        "SELECT purpose, COUNT(*) AS count "
        f"FROM transfers {where} GROUP BY purpose ORDER BY count DESC LIMIT 1", params)
    return {
        "start_date": start_date,
        "end_date": end_date,
        **base,
        "biggest_transfer": biggest,
        "busiest_channel": top_channel,
        "top_purpose": top_purpose,
    }


@mcp.tool()
def search_transfers(
    beneficiary: Optional[str] = None,
    purpose: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    limit: int = 100,
) -> list[dict]:
    """Search IMPS transfers by beneficiary substring, purpose and/or amount
    range, sorted by amount descending. Answers 'biggest transfers to
    Rahul' or 'IMPS transfers above 50000'."""
    clauses, params = [], []
    if beneficiary:
        clauses.append("(beneficiary_name LIKE ? OR remarks LIKE ?)")
        params += [f"%{beneficiary}%", f"%{beneficiary}%"]
    if purpose:
        clauses.append("purpose = ?")
        params.append(purpose)
    if min_amount is not None:
        clauses.append("amount >= ?")
        params.append(float(min_amount))
    if max_amount is not None:
        clauses.append("amount <= ?")
        params.append(float(max_amount))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    limit = max(1, min(int(limit), 1000))
    return db.query(
        "SELECT transaction_id, timestamp, beneficiary_name, amount, purpose, "
        "channel, status, rrn FROM transfers "
        f"{where} ORDER BY amount DESC LIMIT ?",
        [*params, limit],
    )


@mcp.tool()
def get_monthly_transfer_trend(start_date: str, end_date: str) -> list[dict]:
    """Monthly IMPS transfer totals across a date range, ordered
    chronologically. Successful transfers only. Answers 'what is the IMPS
    transfer trend over the last six months?'."""
    clauses, params = _date_clause(start_date, end_date)
    clauses += ["status = 'SUCCESS'"]
    where = "WHERE " + " AND ".join(clauses)
    return db.query(
        "SELECT strftime('%Y-%m', timestamp) AS month, "
        "ROUND(SUM(amount), 2) AS total, COUNT(*) AS count "
        f"FROM transfers {where} GROUP BY month ORDER BY month",
        params,
    )


@mcp.tool()
def get_breakdown(
    dimension: str,
    start_date: str,
    end_date: str,
    sort_by: str = "total",
    order: str = "desc",
    limit: Optional[int] = None,
) -> list[dict]:
    """Generalized IMPS transfer breakdown grouped by any dimension over a date
    range. `dimension` is one of: purpose, channel, beneficiary, mode
    (transfer_mode), bank. Sorted by `sort_by` ('total' default, 'count',
    'max_amount', 'avg') in `order` ('desc'/'asc'). Omit `limit` for the full
    breakdown, or set it for top-N by that dimension (e.g. dimension='purpose',
    limit=1 -> the single biggest purpose). Successful transfers only. One tool
    for 'transfers by purpose', 'top 3 channels', 'which bank most', etc."""
    key = (dimension or "").lower()
    col = _DIMENSIONS.get(key)
    if col is None:
        raise ValueError(
            f"Unknown dimension {dimension!r}. Valid: {sorted(_DIMENSIONS)}"
        )
    clauses, params = _date_clause(start_date, end_date)
    clauses += ["status = 'SUCCESS'"]
    where = "WHERE " + " AND ".join(clauses)
    sql = (
        f"SELECT {col} AS label, ROUND(SUM(amount), 2) AS total, "
        "COUNT(*) AS count, ROUND(MAX(amount), 2) AS max_amount, "
        "ROUND(AVG(amount), 2) AS avg_amount "
        f"FROM transfers {where} GROUP BY {col} "
        f"ORDER BY {_order_by(sort_by, order)}"
    )
    if limit is not None:
        sql += " LIMIT ?"
        params = [*params, max(1, min(int(limit), 1000))]
    return db.query(sql, params)


def _period_totals(start_date: str, end_date: str) -> dict:
    clauses, params = _date_clause(start_date, end_date)
    clauses += ["status = 'SUCCESS'"]
    where = "WHERE " + " AND ".join(clauses)
    row = db.query_one(
        "SELECT ROUND(COALESCE(SUM(amount),0),2) AS total_transferred, "
        "COUNT(*) AS transfers, ROUND(COALESCE(AVG(amount),0),2) AS avg_transfer "
        f"FROM transfers {where}", params)
    return {"start_date": start_date, "end_date": end_date, **row}


@mcp.tool()
def compare_periods(
    period_a_start: str,
    period_a_end: str,
    period_b_start: str,
    period_b_end: str,
) -> dict:
    """Compare IMPS transfers between two date ranges (each inclusive
    'YYYY-MM-DD'). Returns totals, counts and averages for period A and B plus
    the absolute and percentage change (A relative to B). Answers 'did I
    transfer more this month than last?'. Successful transfers only."""
    a = _period_totals(period_a_start, period_a_end)
    b = _period_totals(period_b_start, period_b_end)
    diff = round(a["total_transferred"] - b["total_transferred"], 2)
    pct = (round((diff / b["total_transferred"]) * 100, 1)
           if b["total_transferred"] else None)
    return {
        "period_a": a,
        "period_b": b,
        "difference": {
            "total_transferred_change": diff,
            "total_transferred_pct_change": pct,
            "transfers_change": a["transfers"] - b["transfers"],
        },
    }


if __name__ == "__main__":
    mcp.run()
