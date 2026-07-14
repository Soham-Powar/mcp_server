# Transaction Analytics Platform — Local-First AI Chat

A ChatGPT-style web interface that answers natural-language queries about transaction history databases (UPI payments and IMPS bank transfers). Designed as a secure, local prototype for startups, banks, or enterprises to get business intelligence from transaction records. Everything runs locally: a local **Ollama** model reasons over the databases by calling **read-only analytics tools** exposed by Python **MCP servers** backed by **SQLite**. The LLM never writes or sees SQL — it only calls named, typed tools.

```
React (Vite + TS + Tailwind)
        │  POST /chat  ·  GET /models
        ▼
FastAPI backend
        ├── LLM provider layer  (Ollama today; OpenAI / Anthropic pluggable)
        └── MCP client  ──stdio──►  FastMCP servers  ──►  SQLite
```

## Features

- **Model-agnostic LLM layer** — swap providers by implementing a single interface.
- **Dynamic Ollama model discovery** via `/api/tags`.
- **Domain separation via Multiple MCP Servers** — runs separate UPI and IMPS servers side-by-side.
- **Automatic Routing** — uses a fast router LLM to direct questions to the correct database server.
- **Pre-parameterized Analytics Tools** — ten secure analytics tools per server, all read-only (no INSERT/UPDATE/DELETE/DROP/arbitrary SQL — enforced at the connection layer).
- **Dynamic Source Attribution** — responses stream indicating exactly which data source (UPI, IMPS, or both) was queried to answer the prompt.
- **Streaming Responses** with Markdown rendering.
- **Chat Interface** — sidebar with conversations, model selector, mobile responsive layout, and sample prompts.

## Project Structure

```
frontend/     React + Vite + TypeScript + Tailwind chat UI
backend/      FastAPI app, LLM provider layer, MCP client
  llm/        base interface + ollama / openai / anthropic providers
upi_server/   UPI FastMCP server: analytics tools + read-only db layer
imps_server/  IMPS FastMCP server: analytics tools + read-only db layer
database/     schema.sql/seed.py → upi.db, imps_schema.sql/imps_seed.py → imps.db
shared/       config shared by backend and MCP servers
scripts/      run helpers (.sh and .bat)
```

## Prerequisites

- **Python 3.10+**
- **Node.js 18+**
- **[Ollama](https://ollama.com)** installed and running, with at least one tool-capable model pulled, e.g.:

  ```bash
  ollama pull qwen3.5:9b       # main model (or llama3.1, mistral-nemo, etc.)
  ollama pull gemma4:e2b       # small/fast router model (LLM #1)
  ```

  > Tool calling requires a model that supports it. `qwen3.5:9b`, `llama3.1`, and `mistral-nemo` work well for the **main** model; some small models do not support tools. The **router** model (`ROUTER_MODEL`, default `gemma4:e2b`) only returns a JSON array, so a tiny edge model is ideal.

## Setup

### 1. Backend + MCP Servers + Database

```bash
# from the repo root
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# create sample data for both MCP servers (idempotent, prevents duplicates)
python database/seed.py            # UPI   (or: --rows 5000)
python database/imps_seed.py       # IMPS  (or: --rows 3000)

# start the API (auto-seeds on first run; auto-spawns both MCP servers)
uvicorn backend.main:app --reload
# → http://127.0.0.1:8000    (GET /models, POST /chat, GET /health)
```

Or use the helper: `bash scripts/run_backend.sh` (Windows: `scripts\run_backend.bat`).

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173   (proxies /api → http://127.0.0.1:8000)
```

Or: `bash scripts/run_frontend.sh` (Windows: `scripts\run_frontend.bat`).

Open http://localhost:5173, select a model in the top-right selector, and run queries.

## Configuration

Copy `.env.example` to `.env` to override defaults (DB path, Ollama host, default model, ports, CORS). All values have sensible defaults, so `.env` is optional.

## API

`GET /models`
```json
{ "models": ["qwen3.5:9b", "llama3.1", "gemma4:e2b"] }
```

`POST /chat` (streams `text/plain` chunks)
```json
{
  "model": "qwen3.5:9b",
  "messages": [{ "role": "user", "content": "What was the total spending last month?" }]
}
```

## UPI Analytics Tools (`upi_server/`)

| Tool | Purpose |
|------|---------|
| `get_schema()` | Columns, categories, statuses, apps, date range |
| `get_transactions(start_date, end_date, category, status, limit)` | List transactions (newest first) |
| `get_spending_summary(start_date, end_date)` | Total spend, count, avg, success rate |
| `get_category_breakdown(start_date, end_date)` | Spend grouped by category |
| `get_breakdown(dimension, start_date, end_date, sort_by, order, limit)` | **Generalized** breakdown by any dimension (category, merchant, app, city, bank, device, type). Omit `limit` for full, `limit=1` for top one |
| `get_top_merchants(start_date, end_date, limit, sort_by, order)` | Rank payees. `limit=1`=top merchant, `limit=10`=top 10; `sort_by`∈ total/count/max_amount/avg; `order`∈ desc/asc |
| `get_transaction_stats(start_date, end_date)` | Min/max/avg, biggest txn, busiest city, top app |
| `search_transactions(merchant, category, min_amount, max_amount, limit)` | Filtered search by amount desc |
| `get_monthly_spending_trend(start_date, end_date)` | Monthly spend totals |
| `compare_periods(period_a_start, period_a_end, period_b_start, period_b_end)` | Compare two date ranges: totals, counts, avg + % change |

All UPI tools go through `upi_server/db.py`, which opens SQLite with `PRAGMA query_only=ON` and rejects any statement that is not a plain SELECT.

## IMPS Analytics Tools (`imps_server/`)

A second MCP server for account-to-account IMPS transfers, exposed to the LLM under the `imps__` namespace.

| Tool | Purpose |
|------|---------|
| `get_schema()` | Columns, channels, statuses, purposes, modes, date range |
| `get_transfers(start_date, end_date, status, channel, limit)` | List transfers (newest first) |
| `get_transfer_summary(start_date, end_date)` | Total transferred, count, average transfer amount, success rate |
| `get_purpose_breakdown(start_date, end_date)` | Amount grouped by purpose (rent, salary…) |
| `get_channel_breakdown(start_date, end_date)` | Amount grouped by channel |
| `get_breakdown(dimension, start_date, end_date, sort_by, order, limit)` | **Generalized** breakdown by any dimension (purpose, channel, beneficiary, mode, bank). Omit `limit` for full, `limit=1` for top one |
| `get_top_beneficiaries(start_date, end_date, limit, sort_by, order)` | Rank beneficiaries. `limit=1`=top one, `limit=10`=top 10; `sort_by`∈ total/count/max_amount/avg; `order`∈ desc/asc |
| `get_transfer_stats(start_date, end_date)` | Min/max/avg, biggest transfer, busiest channel |
| `search_transfers(beneficiary, purpose, min_amount, max_amount, limit)` | Filtered search |
| `get_monthly_transfer_trend(start_date, end_date)` | Monthly transfer totals |
| `compare_periods(period_a_start, period_a_end, period_b_start, period_b_end)` | Compare two date ranges: totals, counts, avg + % change |

The IMPS server has its own read-only layer (`imps_server/db.py`) and its own database (`database/imps.db`, seeded by `database/imps_seed.py`).

### Tool Design Notes

- **Generalized over one-off.** Ranking and breakdown tools are parameterized so one tool answers many questions. `get_top_merchants(..., limit, sort_by, order)` covers "the biggest" (`limit=1`), "top 10" (`limit=10`), "most frequent" (`sort_by="count"`) and "smallest" (`order="asc"`). `get_breakdown(dimension, ...)` groups by any allowed dimension and doubles as "top-N by that dimension" when you pass `limit`.
- **Injection-safe parameters.** `sort_by`, `order` and `dimension` become SQL keywords/identifiers, so they are resolved through whitelist maps (`_SORT_EXPR`, `_DIMENSIONS`), never interpolated from raw input; an unknown value raises an error. All data values stay bound parameters.
- **Result shape.** List-returning tools come back as one JSON object per row (MCP content blocks), i.e. stacked JSON objects, not a single array. The LLM reads this fine; parse iteratively if you consume tool output from code.

## Sample Prompts

UPI (routes to the `upi` server):

- What was the total spending last month?
- What are the top merchants by volume?
- Show the biggest transaction details.
- How much amount went to shopping?
- What was the spending trend over the last six months?
- How many failed transactions occurred in June?
- Which city had the highest transaction volume?

IMPS (routes to the `imps` server):

- What is the average IMPS transfer amount this month?
- How much was transferred via IMPS last month?
- Who are the top IMPS beneficiaries?
- How much went to rent through IMPS?
- Which channel is used most for IMPS transfers?
- Show the biggest IMPS transfers.

The router LLM decides which server each question belongs to, so you can ask either kind in the same conversation.

## Multiple MCP Servers + Router (two-LLM routing)

The backend can connect to several MCP servers at once (e.g. a UPI server and an IMPS server). A small **router LLM** classifies each question to the relevant server(s), and only that server's tools are handed to the main model.

```
                    ┌──► upi  MCP server (upi__get_spending_summary, ...)
question ─► router ─┤
          (LLM #1)  └──► imps MCP server (imps__get_transfer_summary, ...)
                               │
                    main model (LLM #2) calls the chosen tools
```

- Tools are namespaced as `<server>__<tool>` so names never collide.
- Routing is **auto-skipped** when there's a single server, or set `ROUTER_ENABLED=false` to always expose every server's tools.
- Configure servers via the `MCP_SERVERS` env var (JSON array of `{name, command, script, description}`) or edit `_DEFAULT_SERVERS` in `shared/config.py`. The router reads each server's `description` to decide.

**Add another MCP server** — write a second FastMCP server, add an entry to `MCP_SERVERS` with a clear `description`, and restart the backend. No frontend changes, no router code changes.

## Extending

**Add a new analytics tool** — add a `@mcp.tool()` function in `upi_server/server.py`. It is auto-discovered and offered to the model; the frontend needs no changes.

**Add a new LLM provider** — implement `LLMProvider` (see `backend/llm/base.py`) in a new file, wire it into `backend/llm/factory.py`, and set `LLM_PROVIDER` in `.env`. Stubs for OpenAI and Anthropic are already in `backend/llm/`. Note the interface also requires `complete()` (used by the router).

## Notes

- v1 intentionally ships **no charts** — the focus is a clean conversational experience.
- The seed data is synthetic and generated deterministically (seed=42).
