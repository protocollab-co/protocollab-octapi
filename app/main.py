from __future__ import annotations

import uuid
from pathlib import Path
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from httpx import HTTPError

from app.config import get_settings
from app.models import (
    AskRequest,
    AttemptHistoryItem,
    FeedbackItem,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    SessionState,
)
from app.services.error_mapper import NormalizedValidationError
from app.services.ollama_client import OllamaClient
from app.services.session_store import SessionStore, SessionStoreError
from app.services.yaml_pipeline import YamlValidationPipeline

_APP_ROOT = Path(__file__).resolve().parent.parent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MAX_LOGGED_MODEL_OUTPUT_CHARS = 1200

settings = get_settings()
ollama = OllamaClient(
    base_url=settings.ollama_base_url,
    model=settings.ollama_model,
    timeout_seconds=settings.ollama_timeout_seconds,
)
_schema_path = str(_APP_ROOT / settings.schema_path) if not Path(settings.schema_path).is_absolute() else settings.schema_path
pipeline = YamlValidationPipeline(schema_path=_schema_path)
session_store = SessionStore()
system_prompt = (_APP_ROOT / "prompts" / "yaml_generation.md").read_text(encoding="utf-8")

app = FastAPI(title="LocalScript YAML API", version="0.1.0")


def _to_feedback_item(exc: NormalizedValidationError) -> FeedbackItem:
    return FeedbackItem(
        field=exc.field,
        message=exc.message,
        expected=exc.expected,
        got=exc.got,
        hint=exc.hint,
        source=exc.source,
    )


def _build_follow_up_prompt(session: SessionState, question: str | None) -> str:
    prompt = session.original_prompt
    if question:
        prompt = f"{prompt}\n\nUser clarification:\n{question}"

    if session.history and session.history[-1].feedback:
        last_feedback = session.history[-1].feedback[0]
        prompt = (
            f"{prompt}\n\nFix previous validation issue:\n"
            f"field={last_feedback.field}; source={last_feedback.source}; "
            f"message={last_feedback.message}; expected={last_feedback.expected}; "
            f"got={last_feedback.got}; hint={last_feedback.hint}"
        )

    return prompt


async def _run_single_attempt(session: SessionState, prompt: str) -> GenerateResponse:
    attempt_number = session.attempts + 1
    logger.info(
        "[SESSION] session_id=%s attempt=%s/%s start",
        session.session_id,
        attempt_number,
        session.max_attempts,
    )
    raw = await ollama.generate_yaml_text(
        prompt=prompt,
        context=session.context,
        system_prompt=system_prompt,
    )
    logger.info(
        "[OLLAMA] session_id=%s attempt=%s raw output (truncated=%s): %s",
        session.session_id,
        attempt_number,
        len(raw) > MAX_LOGGED_MODEL_OUTPUT_CHARS,
        raw[:MAX_LOGGED_MODEL_OUTPUT_CHARS],
    )

    try:
        parsed = pipeline.parse_and_validate(raw)
        session.attempts = attempt_number
        session.yaml = parsed
        session.history.append(AttemptHistoryItem(attempt=attempt_number, prompt=prompt, yaml=parsed))
        session_store.update(session)
        logger.info(
            "[SESSION] session_id=%s attempt=%s success",
            session.session_id,
            attempt_number,
        )
        return GenerateResponse(
            session_id=session.session_id,
            yaml=parsed,
            attempts=session.attempts,
            is_complete=True,
            feedback=[],
        )
    except NormalizedValidationError as exc:
        feedback = _to_feedback_item(exc)
        session.attempts = attempt_number
        session.yaml = None
        session.history.append(
            AttemptHistoryItem(
                attempt=attempt_number,
                prompt=prompt,
                yaml=None,
                feedback=[feedback],
            )
        )
        session_store.update(session)
        logger.warning(
            "[SESSION] session_id=%s attempt=%s failed source=%s field=%s message=%s",
            session.session_id,
            attempt_number,
            feedback.source,
            feedback.field,
            feedback.message,
        )
        return GenerateResponse(
            session_id=session.session_id,
            yaml=None,
            attempts=session.attempts,
            is_complete=False,
            feedback=[feedback],
        )


def _raise_controlled_session_error(
    status_code: int,
    code: str,
    message: str,
    session: SessionState | None = None,
    feedback: list[FeedbackItem] | None = None,
) -> None:
    def _feedback_to_dict(item: FeedbackItem) -> dict[str, object]:
        if hasattr(item, "model_dump"):
            return item.model_dump()
        return item.dict()

    detail: dict[str, object] = {"code": code, "message": message}
    if session is not None:
        detail["session_id"] = session.session_id
        detail["attempts"] = session.attempts
        detail["max_attempts"] = session.max_attempts
    if feedback:
        detail["feedback"] = [_feedback_to_dict(item) for item in feedback]
    raise HTTPException(status_code=status_code, detail=detail)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(str(_APP_ROOT / "templates" / "index.html"))


@app.get(
    "/health",
    responses={503: {"description": "Ollama unavailable"}},
)
async def health() -> HealthResponse:
    try:
        is_ready = await ollama.health()
        return HealthResponse(
            status="ok" if is_ready else "degraded",
            ollama="available" if is_ready else "model_not_found",
            model=settings.ollama_model,
        )
    except HTTPError as exc:
        logger.exception("[OLLAMA] Health check failed")
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {exc}") from exc


@app.post(
    "/generate",
    responses={
        409: {"description": "Controlled session error"},
        500: {"description": "Internal error"},
        503: {"description": "Ollama unavailable"},
    },
)
async def generate(payload: GenerateRequest) -> GenerateResponse:
    try:
        session = SessionState(
            session_id=uuid.uuid4().hex,
            original_prompt=payload.prompt,
            context=payload.context,
        )
        session_store.create(session)
        logger.info("[SESSION] Created session_id=%s", session.session_id)
        return await _run_single_attempt(session=session, prompt=payload.prompt)
    except HTTPError as exc:
        logger.exception("[OLLAMA] Generate call failed")
        raise HTTPException(status_code=503, detail=f"Ollama request failed: {exc}") from exc
    except Exception as exc:
        logger.exception("[UNEXPECTED] Unhandled error")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


@app.post(
    "/ask",
    responses={
        404: {"description": "Session not found"},
        409: {"description": "Controlled session error"},
        500: {"description": "Internal error"},
        503: {"description": "Ollama unavailable"},
    },
)
async def ask(payload: AskRequest) -> GenerateResponse:
    try:
        session = session_store.get(payload.session_id)
        if session.yaml is not None:
            _raise_controlled_session_error(
                status_code=409,
                code="already_completed",
                message="Session already completed with valid YAML.",
                session=session,
            )

        session_store.assert_not_exhausted(session)

        if session.context is None:
            session.context = {}
        session.context["last_user_question"] = payload.question

        prompt = _build_follow_up_prompt(session=session, question=payload.question)
        result = await _run_single_attempt(session=session, prompt=prompt)
        if not result.is_complete and session.attempts >= session.max_attempts:
            _raise_controlled_session_error(
                status_code=409,
                code="attempt_limit_reached",
                message="Attempt limit reached. Start a new session with /generate.",
                session=session,
                feedback=result.feedback,
            )
        return result
    except SessionStoreError as exc:
        status_code = 404 if exc.code == "not_found" else 409
        raise HTTPException(status_code=status_code, detail={"code": exc.code, "message": exc.message}) from exc
    except HTTPError as exc:
        logger.exception("[OLLAMA] Ask call failed")
        raise HTTPException(status_code=503, detail=f"Ollama request failed: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("[UNEXPECTED] Unhandled error")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc
