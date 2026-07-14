"""FastAPI backend: model discovery + streaming chat over MCP analytics.

Endpoints:
    GET  /models   -> ["qwen3", "llama3.1", ...]
    POST /chat     -> streams the assistant's answer as plain-text chunks
    GET  /health   -> liveness probe
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared import config  # noqa: E402
from backend.models import ChatRequest, ModelsResponse  # noqa: E402
from backend.mcp_client import mcp_client  # noqa: E402
from backend.llm.factory import get_provider  # noqa: E402
from backend import router as router_mod  # noqa: E402


def _system_prompt() -> str:
    today = dt.date.today().isoformat()
    return (
        "You are a helpful transactions analytics assistant designed to help startups, banks, and enterprises analyze transaction databases.\n"
        f"Today's date is {today}.\n\n"
        "The database transaction history (both UPI payments and IMPS bank transfers) is available "
        "ONLY through the provided analytics tools — you cannot see or access the raw data otherwise.\n"
        "When a query needs database insights, call the appropriate tool. Resolve relative dates (e.g. 'last month', "
        "'June', 'last six months') to concrete YYYY-MM-DD ranges before calling a tool. If unsure what data "
        "exists, call the server's get_schema first. All amounts are in Indian Rupees (₹).\n\n"
        "CRITICAL SAFETY & CORRECTNESS RULES:\n"
        "1. Never claim, assume, or make up a value you did not obtain directly from a tool response.\n"
        "2. If there is no possible tool call or combination of calls that can answer the query (e.g., "
        "no matching tool exists, or parameter ranges cannot be resolved), you MUST explicitly state that you cannot "
        "answer the query with the available tools, and briefly explain why. Do NOT make up or hallucinate any numbers or summaries.\n"
        "3. Answer concisely in Markdown; show key numbers clearly."
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await mcp_client.connect()
    yield
    await mcp_client.close()


app = FastAPI(title="Transaction Analytics API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/models", response_model=ModelsResponse)
async def models() -> ModelsResponse:
    provider = get_provider()
    try:
        names = await provider.list_models()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not reach {provider.name}: {exc}",
        )
    return ModelsResponse(models=names)


@app.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    provider = get_provider()

    # Prepend the system prompt if the client did not supply one.
    convo = [m.model_dump(exclude_none=True) for m in req.messages]
    if not convo or convo[0].get("role") != "system":
        convo.insert(0, {"role": "system", "content": _system_prompt()})

    # --- Routing (LLM #1): pick which MCP server(s) can answer this ------
    # Skipped automatically when there is one server or ROUTER_ENABLED=false.
    specs = mcp_client.server_specs()
    if config.ROUTER_ENABLED and len(specs) > 1:
        question = router_mod.latest_user_question(convo)
        selected = await router_mod.route(
            provider, config.ROUTER_MODEL, specs, question
        )
    else:
        selected = mcp_client.server_names

    # Expose only the selected servers' tools to the main model (LLM #2).
    tools = await mcp_client.list_tools(selected)

    async def token_stream():
        try:
            async for chunk in provider.stream_chat(
                model=req.model,
                messages=convo,
                tools=tools,
                tool_executor=mcp_client.call_tool,
                temperature=req.temperature,
            ):
                yield chunk
        except Exception as exc:  # stream the error rather than 500
            yield f"\n\n[error] {exc}"

    return StreamingResponse(
        token_stream(),
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
