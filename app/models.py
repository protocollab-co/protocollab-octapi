from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1)
    context: dict[str, Any] | None = None


class AskRequest(BaseModel):
    session_id: str = Field(min_length=1)
    question: str = Field(min_length=1)


class ExecuteRequest(BaseModel):
    session_id: str | None = None
    yaml: dict[str, Any] | None = None
    context: dict[str, Any] | None = None


class ValidationErrorResponse(BaseModel):
    field: str
    message: str
    expected: str
    got: str
    hint: str
    source: str
    attempts: int = 1


class FeedbackItem(BaseModel):
    field: str
    message: str
    expected: str
    got: str
    hint: str
    source: str


class GenerateResponse(BaseModel):
    session_id: str
    yaml: dict[str, Any] | None = None
    attempts: int = 1
    is_complete: bool = False
    feedback: list[FeedbackItem] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    status: str
    stdout: str
    stderr: str
    exit_code: int


class ExecuteResponse(BaseModel):
    session_id: str | None = None
    operation: str
    lua_code: str
    execution_result: ExecutionResult


class AttemptHistoryItem(BaseModel):
    attempt: int
    prompt: str
    yaml: dict[str, Any] | None = None
    feedback: list[FeedbackItem] = Field(default_factory=list)


class SessionState(BaseModel):
    session_id: str
    attempts: int = 0
    max_attempts: int = 3
    original_prompt: str
    context: dict[str, Any] | None = None
    history: list[AttemptHistoryItem] = Field(default_factory=list)
    yaml: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: str
    ollama: str
    model: str
    docker: str | None = None
