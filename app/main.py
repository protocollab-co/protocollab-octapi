from __future__ import annotations

import uuid
from pathlib import Path
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from httpx import HTTPError

from app.config import get_settings
from app.models import (
    AskRequest,
    AttemptHistoryItem,
    ExecuteRequest,
    ExecuteResponse,
    FeedbackItem,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    ModelListResponse,
    ModelSelectRequest,
    ProfileListResponse,
    ProfileOption,
    ProfileSelectRequest,
    SessionState,
)
from app.services.error_mapper import NormalizedValidationError
from app.services.lua_codegen import LuaCodeGenerator
from app.services.lua_validator import LuaCodeValidator
from app.services.ollama_client import OllamaClient
from app.services.sandbox_executor import DockerSandboxExecutor
from app.services.session_store import SessionStore, SessionStoreError
from app.services.template_selector import TemplateSelector
from app.services.yaml_pipeline import YamlValidationPipeline

_APP_ROOT = Path(__file__).resolve().parent.parent


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MAX_LOGGED_MODEL_OUTPUT_CHARS = 1200
UNEXPECTED_LOG_MESSAGE = "[UNEXPECTED] Unhandled error"

settings = get_settings()
ollama = OllamaClient(
    base_url=settings.ollama_base_url,
    model=settings.ollama_model,
    timeout_seconds=settings.ollama_timeout_seconds,
)
_schema_path = str(_APP_ROOT / settings.schema_path) if not Path(settings.schema_path).is_absolute() else settings.schema_path
pipeline = YamlValidationPipeline(schema_path=_schema_path)
session_store = SessionStore()
json_system_prompt = (_APP_ROOT / "prompts" / "json_generation.md").read_text(encoding="utf-8")
yaml_system_prompt = (_APP_ROOT / "prompts" / "yaml_generation.md").read_text(encoding="utf-8")
_templates_dir = str(_APP_ROOT / settings.templates_dir) if not Path(settings.templates_dir).is_absolute() else settings.templates_dir
_templates_count = len(list(Path(_templates_dir).glob("*.jinja2")))
_GENERATION_PROFILES: dict[str, dict[str, str]] = {
    "balanced": {
        "label": "Balanced",
        "description": "Стандартный режим генерации без усиленных ограничений.",
        "generate_suffix": "",
        "follow_up_suffix": "",
    },
    "strict-json": {
        "label": "Strict JSON",
        "description": "Максимально прижимает первую генерацию к schema-valid JSON.",
        "generate_suffix": (
            "\n\nProfile mode: Strict JSON. Prefer the simplest schema-valid object. "
            "Avoid optional structure changes and keep field values deterministic."
        ),
        "follow_up_suffix": (
            "\n\nProfile mode: Strict JSON follow-up. Make the smallest possible correction and preserve intent."
        ),
    },
    "literal-fields": {
        "label": "Literal Fields",
        "description": "Строже удерживает path-like поля и типы параметров.",
        "generate_suffix": (
            "\n\nProfile mode: Literal Fields. Keep path-like values as plain strings only. "
            "Do not rewrite source paths into helper objects, arrays, or templates."
        ),
        "follow_up_suffix": (
            "\n\nProfile mode: Literal Fields follow-up. Preserve existing path-like field values and fix only invalid types or names."
        ),
    },
}
_active_generation_profile = "balanced"
template_selector = TemplateSelector(templates_dir=_templates_dir)
lua_codegen = LuaCodeGenerator(templates_dir=_templates_dir)
lua_validator = LuaCodeValidator(
    docker_image=settings.docker_image,
    timeout_seconds=settings.sandbox_timeout_seconds,
    memory_mb=settings.sandbox_memory_mb,
    network_mode=settings.sandbox_network_mode,
)
sandbox_executor = DockerSandboxExecutor(
    docker_image=settings.docker_image,
    timeout_seconds=settings.sandbox_timeout_seconds,
    memory_mb=settings.sandbox_memory_mb,
    network_mode=settings.sandbox_network_mode,
)

app = FastAPI(title="LocalScript YAML API", version="0.1.0")
app.mount("/hljs", StaticFiles(directory=str(_APP_ROOT / "templates" / "hljs")), name="hljs")


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


def _build_profiled_system_prompt(base_prompt: str, phase: str) -> str:
    profile = _GENERATION_PROFILES.get(_active_generation_profile, _GENERATION_PROFILES["balanced"])
    suffix_key = "generate_suffix" if phase == "generate" else "follow_up_suffix"
    suffix = profile.get(suffix_key, "")
    return f"{base_prompt}{suffix}" if suffix else base_prompt


def _list_profile_options() -> list[ProfileOption]:
    return [
        ProfileOption(id=profile_id, label=item["label"], description=item["description"])
        for profile_id, item in _GENERATION_PROFILES.items()
    ]


def _build_diagnostic_lua(raw_output: str, feedback: FeedbackItem) -> str:
    lines = [
        "-- Diagnostic Lua fallback",
        "-- YAML validation/codegen did not complete successfully.",
        f"-- field: {feedback.field}",
        f"-- source: {feedback.source}",
        f"-- message: {feedback.message}",
        f"-- expected: {feedback.expected}",
        f"-- got: {feedback.got}",
    ]
    if feedback.hint:
        lines.append(f"-- hint: {feedback.hint}")
    lines.append("-- raw_model_output:")
    for line in raw_output.splitlines()[:60]:
        lines.append(f"-- {line}")
    lines.append("return nil")
    return "\n".join(lines) + "\n"


async def _run_single_attempt(session: SessionState, prompt: str, system_prompt: str) -> GenerateResponse:
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
        operation = str(parsed.get("operation", ""))
        params_obj = parsed.get("parameters", {})
        params = params_obj if isinstance(params_obj, dict) else {}
        template_path = template_selector.select_template(operation)
        generated_lua = lua_codegen.generate_code(
            operation=operation,
            params=params,
            template_path=template_path,
        )

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
            lua_code=generated_lua,
            raw_model_output=raw,
            attempts=session.attempts,
            is_complete=True,
            feedback=[],
        )
    except NormalizedValidationError as exc:
        feedback = _to_feedback_item(exc)
        generated_lua = _build_diagnostic_lua(raw_output=raw, feedback=feedback)
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
            lua_code=generated_lua,
            raw_model_output=raw,
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


def _resolve_execute_input(payload: ExecuteRequest) -> tuple[str | None, dict[str, object], dict[str, object] | None]:
    if payload.session_id and payload.yaml is not None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_execute_payload",
                "message": "Provide either session_id or yaml, not both.",
            },
        )

    if payload.session_id:
        session = session_store.get(payload.session_id)
        if session.yaml is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "session_not_ready",
                    "message": "Session has no valid YAML yet. Complete /generate or /ask first.",
                    "session_id": session.session_id,
                    "attempts": session.attempts,
                },
            )

        yaml_payload = session.yaml
        context_payload = payload.context if payload.context is not None else session.context
        return session.session_id, yaml_payload, context_payload

    if payload.yaml is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "invalid_execute_payload",
                "message": "Provide session_id or yaml for /execute.",
            },
        )

    return None, payload.yaml, payload.context


def _execute_yaml_contract(
    yaml_payload: dict[str, object],
    context_payload: dict[str, object] | None,
    session_id: str | None,
) -> ExecuteResponse:
    operation = str(yaml_payload.get("operation", ""))
    params_obj = yaml_payload.get("parameters", {})
    params = params_obj if isinstance(params_obj, dict) else {}

    template_path = template_selector.select_template(operation)
    lua_code = lua_codegen.generate_code(operation=operation, params=params, template_path=template_path)
    lua_validator.validate_syntax(lua_code)
    execution_result = sandbox_executor.execute(lua_code=lua_code, context=context_payload)
    return ExecuteResponse(
        session_id=session_id,
        operation=operation,
        lua_code=lua_code,
        execution_result=execution_result,
    )


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
            model=ollama.model,
            docker="available" if sandbox_executor.is_available() else "unavailable",
            templates_count=_templates_count,
        )
    except HTTPError as exc:
        logger.exception("[OLLAMA] Health check failed")
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {exc}") from exc


@app.get(
    "/models",
    responses={503: {"description": "Ollama unavailable"}},
)
async def list_models() -> ModelListResponse:
    try:
        models = await ollama.list_models()
        return ModelListResponse(active_model=ollama.model, models=models)
    except HTTPError as exc:
        logger.exception("[OLLAMA] Model list request failed")
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {exc}") from exc


@app.post(
    "/models/select",
    responses={400: {"description": "Model not found"}, 503: {"description": "Ollama unavailable"}},
)
async def select_model(payload: ModelSelectRequest) -> ModelListResponse:
    try:
        models = await ollama.list_models()
    except HTTPError as exc:
        logger.exception("[OLLAMA] Model selection failed during model list request")
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {exc}") from exc

    if payload.model not in models:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "model_not_found",
                "message": "Requested model is not available in Ollama.",
                "model": payload.model,
                "available_models": models,
            },
        )

    ollama.set_model(payload.model)
    return ModelListResponse(active_model=ollama.model, models=models)


@app.get("/profiles")
async def list_profiles() -> ProfileListResponse:
    return ProfileListResponse(active_profile=_active_generation_profile, profiles=_list_profile_options())


@app.post(
    "/profiles/select",
    responses={400: {"description": "Unknown profile"}},
)
async def select_profile(payload: ProfileSelectRequest) -> ProfileListResponse:
    global _active_generation_profile

    if payload.profile_id not in _GENERATION_PROFILES:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "profile_not_found",
                "message": "Requested generation profile is not available.",
                "profile_id": payload.profile_id,
                "available_profiles": list(_GENERATION_PROFILES.keys()),
            },
        )

    _active_generation_profile = payload.profile_id
    return ProfileListResponse(active_profile=_active_generation_profile, profiles=_list_profile_options())


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
        return await _run_single_attempt(
            session=session,
            prompt=payload.prompt,
            system_prompt=_build_profiled_system_prompt(json_system_prompt, phase="generate"),
        )
    except HTTPError as exc:
        logger.exception("[OLLAMA] Generate call failed")
        raise HTTPException(status_code=503, detail=f"Ollama request failed: {exc}") from exc
    except Exception as exc:
        logger.exception(UNEXPECTED_LOG_MESSAGE)
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

        if payload.auto_correction:
            session_store.assert_not_exhausted(session)

        if session.context is None:
            session.context = {}
        session.context["last_user_question"] = payload.question

        prompt = _build_follow_up_prompt(session=session, question=payload.question)
        result = await _run_single_attempt(
            session=session,
            prompt=prompt,
            system_prompt=_build_profiled_system_prompt(yaml_system_prompt, phase="follow_up"),
        )
        if payload.auto_correction and not result.is_complete and session.attempts >= session.max_attempts:
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
        logger.exception(UNEXPECTED_LOG_MESSAGE)
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


@app.post(
    "/execute",
    responses={
        400: {"description": "Invalid execute payload"},
        404: {"description": "Session not found"},
        409: {"description": "Controlled execution error"},
        500: {"description": "Internal error"},
    },
)
async def execute(payload: ExecuteRequest) -> ExecuteResponse:
    try:
        session_id, yaml_payload, context_payload = _resolve_execute_input(payload)
        return _execute_yaml_contract(
            yaml_payload=yaml_payload,
            context_payload=context_payload,
            session_id=session_id,
        )
    except SessionStoreError as exc:
        status_code = 404 if exc.code == "not_found" else 409
        raise HTTPException(status_code=status_code, detail={"code": exc.code, "message": exc.message}) from exc
    except NormalizedValidationError as exc:
        raise HTTPException(status_code=409, detail=exc.as_dict()) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(UNEXPECTED_LOG_MESSAGE)
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc
