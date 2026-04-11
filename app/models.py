from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    context: dict[str, Any] | None = None


class ValidationErrorResponse(BaseModel):
    field: str
    message: str
    expected: str
    got: str
    hint: str
    source: str
    attempts: int = 1


class GenerateResponse(BaseModel):
    yaml: dict[str, Any]
    attempts: int = 1


class HealthResponse(BaseModel):
    status: str
    ollama: str
    model: str
