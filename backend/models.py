"""Pydantic request/response models for the backend API."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


class ChatMessage(BaseModel):
    role: Role
    content: str = ""
    # Optional fields used when replaying tool calls back to a provider.
    name: Optional[str] = None
    tool_call_id: Optional[str] = None


class ChatRequest(BaseModel):
    model: str = Field(..., description="Model name, e.g. 'qwen3'")
    messages: list[ChatMessage]
    temperature: float = 0.7


class ModelsResponse(BaseModel):
    models: list[str]


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]
