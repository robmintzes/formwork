# schemas.py
# Pydantic models for the response envelope.

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentContext(BaseModel):
    title: Optional[str] = None
    path: Optional[str] = None
    is_workshared: bool = False


class ErrorDetail(BaseModel):
    code: str
    message: str
    checks: list[str] = Field(default_factory=list)


class RevitResponse(BaseModel):
    """
    Standard response envelope returned by all pyRevit Routes endpoints
    and normalized by the MCP server before returning to clients.
    """

    status: str  # "ok" | "warning" | "error"
    tool: str
    risk_class: str = "read_only"
    document: DocumentContext = Field(default_factory=DocumentContext)
    data: dict[str, Any] = Field(default_factory=dict)
    messages: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    error: Optional[ErrorDetail] = None

    @property
    def is_ok(self) -> bool:
        return self.status == "ok"

    @property
    def is_error(self) -> bool:
        return self.status == "error"
