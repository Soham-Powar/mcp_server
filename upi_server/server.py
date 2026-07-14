"""FastMCP server exposing business-level UPI analytics tools.

The LLM never sees or writes SQL. It only sees these named tools with
typed parameters. Every tool builds a parameterized SELECT internally and
runs it through the read-only db layer.

Run standalone (stdio transport):
    python upi_server/server.py
"""
from __future__ import annotations

import os
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from upi_server import db  # noqa: E402

mcp = FastMCP("upi-analytics")

# --- Helpers --------------------------------------------------------------

_DATE_FILTER = "timestamp >= ? AND timestamp < datetime(?, '+1 day')"


def _date_clause(start_date: Optional[str], end_date: Optional[str]):
    """Return (sql_fragment, params) for an inclusive [start, end] range."""
    clauses, params = [], []
    if start_date:
        clauses.append("timestamp >= ?")
        params.append(start_date)
    if end_date:
        # inclusive of the end day
        clauses.append("timestamp < datetime(?, '+1 day')")
        params.append(end_date)
    return clauses, params


# Whitelisted sort expressions. `sort_by` and `order` become SQL keywords, so
# they are NEVER interpolated from raw input — only resolved through these maps.
_SORT_EXPR = {
    "total": "SUM(amount)",
    "count": "COUNT(*)",
    "max_amount": "MAX(amount)",
    "avg": "AVG(amount)",
}

# Dimensions the generalized breakdown can group by -> real column.
_DIMENSIONS = {
    "category": "transaction_category",
    "merchant": "payee_vpa",
    "payee": "payee_vpa",
    "payment_app": "payment_app",
    "app": "payment_app",
    "location": "location",
    "city": "location",
    "bank": "payee_bank",
    "device": "device_type",
    "type": "transaction_type",
}


def _order_by(sort_by: Optional[str], order: Optional[str]) -> str:
    expr = _SORT_EXPR.get((sort_by or "total").lower(), _SORT_EXPR["total"])
    direction = "ASC" if (order or "desc").lower() == "asc" else "DESC"
    return f"{expr} {direction}"


# --- Tools ----------------------------------------------------------------


@mcp.tool()
def get_schema() -> dict:
    """Return the transactions table schema: column names, types and the
    distinct values available for the categorical fields. Call this first
    when you need to know what data exists."""
    cols = db.query("SELECT name, type FROM pragma_table_info('transactions')")
    categories = [r["transaction_category"] for r in db.query(
        "SELECT DISTINCT transaction_category FROM transactions "
        "WHERE transaction_category IS NOT NULL ORDER BY 1")]
    statuses = [r["status"] for r in db.query(
        "SELECT DISTINCT status FROM transactions ORDER BY 1")]
    apps = [r["payment_app"] for r in db.query(
        "SELECT DISTINCT payment_app FROM transactions ORDER BY 1")]
    rng = db.query_one(
        "SELECT MIN(timestamp) AS min_ts, MAX(timestamp) AS max_ts, "
        "COUNT(*) AS total FROM transactions")
    return {
        "table": "transactions",
        "columns": cols,
        "categories": categories,
        "statuses": statuses,
        "payment_apps": apps,
        "date_range": {"start": rng["min_ts"], "end": rng["max_ts"]},
        "row_count": rng["total"],
    }


@mcp.tool()
def get_transactions(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """List individual transactions with optional filters. Dates are
    'YYYY-MM-DD' and inclusive. Returns newest first. Use for questions
    like 'show transactions in June' or 'biggest transactions'
    (sort by amount is not applied here — use search_transactions for
    amount filtering)."""
    clauses, params = _date_clause(start_date, end_date)
    if category:
        clauses.append("transaction_category = ?")
        params.append(category)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    limit = max(1, min(int(limit), 1000))
    sql = (
        "SELECT transaction_id, timestamp, payer_vpa, payee_vpa, amount, "
        "transaction_type, transaction_category, status, payment_app, "
        "location, remarks FROM transactions "
        f"{where} ORDER BY timestamp DESC LIMIT ?"
    )
    return db.query(sql, [*params, limit])


@mcp.tool()
def get_spending_summary(start_date: str, end_date: str) -> dict:
    """Total spend, transaction count, average ticket size and success rate
    over a date range (inclusive, 'YYYY-MM-DD'). Spend counts successful
    DEBIT transactions only. Answers 'how much was spent last month?'."""
    clauses, params = _date_clause(start_date, end_date)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    row = db.query_one(
        "SELECT "
        "COALESCE(SUM(CASE WHEN status='SUCCESS' AND transaction_type='DEBIT' "
        "  THEN amount END), 0) AS total_spent, "
        "COUNT(*) AS total_transactions, "
        "SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END) AS successful, "
        "SUM(CASE WHEN status='FAILED' THEN 1 ELSE 0 END) AS failed, "
        "COALESCE(AVG(CASE WHEN status='SUCCESS' AND transaction_type='DEBIT' "
        "  THEN amount END), 0) AS avg_transaction "
        f"FROM transactions {where}",
        params,
    )
    total = row["total_transactions"] or 0
    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_spent": round(row["total_spent"], 2),
        "total_transactions": total,
        "successful": row["successful"],
        "failed": row["failed"],
        "avg_transaction": round(row["avg_transaction"], 2),
        "success_rate": round((row["successful"] / total) * 100, 1) if total else 0,
    }


@mcp.tool()
def get_category_breakdown(start_date: str, end_date: str) -> list[dict]:
    """Spend grouped by transaction_category over a date range, sorted by
    total descending. Answers 'how much went to shopping?' or 'what is the
    spending breakdown?'. Successful DEBIT transactions only."""
    clauses, params = _date_clause(start_date, end_date)
    clauses += ["status = 'SUCCESS'", "transaction_type = 'DEBIT'"]
    where = "WHERE " + " AND ".join(clauses)
    return db.query(
        "SELECT transaction_category AS category, "
        "ROUND(SUM(amount), 2) AS total, COUNT(*) AS count, "
        "ROUND(AVG(amount), 2) AS avg_amount "
        f"FROM transactions {where} "
        "GROUP BY transaction_category ORDER BY total DESC",
        params,
    )


@mcp.tool()
def get_top_merchants(
    start_date: str,
    end_date: str,
    limit: int = 10,
    sort_by: str = "total",
    order: str = "desc",
) -> list[dict]:
    """Rank payees (merchants) over a date range. Generalized ranking:
    `limit=1` returns the single top merchant, `limit=10` the top 10.
    `sort_by` is one of 'total' (summed amount, default), 'count' (number of
    payments), 'max_amount' (largest single payment) or 'avg' (average
    payment). `order` is 'desc' (default) or 'asc' (e.g. smallest / least
    frequent). Successful DEBIT transactions only. Answers 'top merchants',
    'who did I pay the most', 'my most frequent merchant', 'smallest payee'."""
    clauses, params = _date_clause(start_date, end_date)
    clauses += ["status = 'SUCCESS'", "transaction_type = 'DEBIT'"]
    where = "WHERE " + " AND ".join(clauses)
    limit = max(1, min(int(limit), 100))
    return db.query(
        "SELECT payee_vpa AS merchant, "
        "ROUND(SUM(amount), 2) AS total, COUNT(*) AS count, "
        "ROUND(MAX(amount), 2) AS max_amount, ROUND(AVG(amount), 2) AS avg_amount "
        f"FROM transactions {where} "
        f"GROUP BY payee_vpa ORDER BY {_order_by(sort_by, order)} LIMIT ?",
        [*params, limit],
    )


@mcp.tool()
def get_transaction_stats(start_date: str, end_date: str) -> dict:
    """Descriptive stats over a date range: min / max / average amount,
    largest single transaction, busiest location and most-used payment app.
    Answers 'which city had the highest transaction volume?'."""
    clauses, params = _date_clause(start_date, end_date)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    base = db.query_one(
        "SELECT COUNT(*) AS count, ROUND(MIN(amount),2) AS min_amount, "
        "ROUND(MAX(amount),2) AS max_amount, ROUND(AVG(amount),2) AS avg_amount, "
        "ROUND(SUM(amount),2) AS total_amount "
        f"FROM transactions {where}", params)
    biggest = db.query_one(
        "SELECT transaction_id, timestamp, payee_vpa, amount, "
        "transaction_category FROM transactions "
        f"{where} ORDER BY amount DESC LIMIT 1", params)
    top_city = db.query_one(
        "SELECT location, COUNT(*) AS count, ROUND(SUM(amount),2) AS total "
        f"FROM transactions {where} GROUP BY location "
        "ORDER BY count DESC LIMIT 1", params)
    top_app = db.query_one(
        "SELECT payment_app, COUNT(*) AS count "
        f"FROM transactions {where} GROUP BY payment_app "
        "ORDER BY count DESC LIMIT 1", params)
    return {
        "start_date": start_date,
        "end_date": end_date,
        **base,
        "biggest_transaction": biggest,
        "busiest_location": top_city,
        "most_used_app": top_app,
    }


@mcp.tool()
def search_transactions(
    merchant: Optional[str] = None,
    category: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    limit: int = 100,
) -> list[dict]:
    """Search transactions by merchant substring, category and/or amount
    range, sorted by amount descending. Answers 'show the biggest
    transactions' (set min_amount) or 'payments to swiggy'."""
    clauses, params = [], []
    if merchant:
        clauses.append("(payee_vpa LIKE ? OR remarks LIKE ?)")
        params += [f"%{merchant}%", f"%{merchant}%"]
    if category:
        clauses.append("transaction_category = ?")
        params.append(category)
    if min_amount is not None:
        clauses.append("amount >= ?")
        params.append(float(min_amount))
    if max_amount is not None:
        clauses.append("amount <= ?")
        params.append(float(max_amount))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    limit = max(1, min(int(limit), 1000))
    return db.query(
        "SELECT transaction_id, timestamp, payee_vpa, amount, "
        "transaction_category, status, payment_app, location, remarks "
        f"FROM transactions {where} ORDER BY amount DESC LIMIT ?",
        [*params, limit],
    )


@mcp.tool()
def get_monthly_spending_trend(start_date: str, end_date: str) -> list[dict]:
    """Monthly spend totals across a date range, ordered chronologically.
    Answers 'what was the spending trend over the last six months?'.
    Successful DEBIT transactions only."""
    clauses, params = _date_clause(start_date, end_date)
    clauses += ["status = 'SUCCESS'", "transaction_type = 'DEBIT'"]
    where = "WHERE " + " AND ".join(clauses)
    return db.query(
        "SELECT strftime('%Y-%m', timestamp) AS month, "
        "ROUND(SUM(amount), 2) AS total, COUNT(*) AS count "
        f"FROM transactions {where} "
        "GROUP BY month ORDER BY month",
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
    """Generalized spend breakdown grouped by any dimension over a date range.
    `dimension` is one of: category, merchant, payment_app, location/city,
    bank, device, type. Sorted by `sort_by` ('total' default, 'count',
    'max_amount', 'avg') in `order` ('desc'/'asc'). Omit `limit` for the full
    breakdown, or set it to get top-N by that dimension (e.g. dimension='city',
    limit=1 -> the single top city). Successful DEBIT transactions only.
    One tool for 'spend by category', 'top 3 cities', 'which app most', etc."""
    key = (dimension or "").lower()
    col = _DIMENSIONS.get(key)
    if col is None:
        raise ValueError(
            f"Unknown dimension {dimension!r}. Valid: {sorted(_DIMENSIONS)}"
        )
    clauses, params = _date_clause(start_date, end_date)
    clauses += ["status = 'SUCCESS'", "transaction_type = 'DEBIT'"]
    where = "WHERE " + " AND ".join(clauses)
    sql = (
        f"SELECT {col} AS label, ROUND(SUM(amount), 2) AS total, "
        "COUNT(*) AS count, ROUND(MAX(amount), 2) AS max_amount, "
        "ROUND(AVG(amount), 2) AS avg_amount "
        f"FROM transactions {where} GROUP BY {col} "
        f"ORDER BY {_order_by(sort_by, order)}"
    )
    if limit is not None:
        sql += " LIMIT ?"
        params = [*params, max(1, min(int(limit), 1000))]
    return db.query(sql, params)


def _period_totals(start_date: str, end_date: str) -> dict:
    clauses, params = _date_clause(start_date, end_date)
    clauses += ["status = 'SUCCESS'", "transaction_type = 'DEBIT'"]
    where = "WHERE " + " AND ".join(clauses)
    row = db.query_one(
        "SELECT ROUND(COALESCE(SUM(amount),0),2) AS total_spent, "
        "COUNT(*) AS transactions, ROUND(COALESCE(AVG(amount),0),2) AS avg_transaction "
        f"FROM transactions {where}", params)
    return {"start_date": start_date, "end_date": end_date, **row}


@mcp.tool()
def compare_periods(
    period_a_start: str,
    period_a_end: str,
    period_b_start: str,
    period_b_end: str,
) -> dict:
    """Compare spending between two date ranges (each inclusive 'YYYY-MM-DD').
    Returns totals, counts and averages for period A and period B plus the
    absolute and percentage change (A relative to B). Answers 'did I spend
    more this month than last?'. Successful DEBIT transactions only."""
    a = _period_totals(period_a_start, period_a_end)
    b = _period_totals(period_b_start, period_b_end)
    diff = round(a["total_spent"] - b["total_spent"], 2)
    pct = round((diff / b["total_spent"]) * 100, 1) if b["total_spent"] else None
    return {
        "period_a": a,
        "period_b": b,
        "difference": {
            "total_spent_change": diff,
            "total_spent_pct_change": pct,
            "transactions_change": a["transactions"] - b["transactions"],
        },
    }


if __name__ == "__main__":
    mcp.run()
