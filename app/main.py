from __future__ import annotations

from pathlib import Path
import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from httpx import HTTPError

from app.config import get_settings
from app.models import GenerateRequest, GenerateResponse, HealthResponse, ValidationErrorResponse
from app.services.error_mapper import NormalizedValidationError
from app.services.ollama_client import OllamaClient
from app.services.yaml_pipeline import YamlValidationPipeline


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MAX_LOGGED_MODEL_OUTPUT_CHARS = 1200

settings = get_settings()
ollama = OllamaClient(
    base_url=settings.ollama_base_url,
    model=settings.ollama_model,
    timeout_seconds=settings.ollama_timeout_seconds,
)
pipeline = YamlValidationPipeline(schema_path=settings.schema_path)
system_prompt = Path("prompts/yaml_generation.md").read_text(encoding="utf-8")

app = FastAPI(title="LocalScript YAML API", version="0.1.0")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse("templates/index.html")


@app.get("/health", response_model=HealthResponse)
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
    response_model=GenerateResponse,
    responses={400: {"model": ValidationErrorResponse}},
)
async def generate(payload: GenerateRequest) -> GenerateResponse:
    try:
        logger.info("[OLLAMA] Generating YAML from prompt")
        raw = await ollama.generate_yaml_text(
            prompt=payload.prompt,
            context=payload.context,
            system_prompt=system_prompt,
        )
        logger.info(
            "[OLLAMA] Raw model output (truncated=%s): %s",
            len(raw) > MAX_LOGGED_MODEL_OUTPUT_CHARS,
            raw[:MAX_LOGGED_MODEL_OUTPUT_CHARS],
        )
        logger.info("[YAML_PIPELINE] Parsing and validating generated YAML")
        parsed = pipeline.parse_and_validate(raw)
        return GenerateResponse(yaml=parsed, attempts=1)
    except NormalizedValidationError as exc:
        logger.warning("[%s] %s", exc.source.upper(), exc.message)
        raise HTTPException(status_code=400, detail=exc.as_dict(attempts=1)) from exc
    except HTTPError as exc:
        logger.exception("[OLLAMA] Generate call failed")
        raise HTTPException(status_code=503, detail=f"Ollama request failed: {exc}") from exc
    except Exception as exc:
        logger.exception("[UNEXPECTED] Unhandled error")
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc
