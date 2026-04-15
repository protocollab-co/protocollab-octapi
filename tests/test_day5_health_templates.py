"""
Day 5 Tests — Health Endpoint & Template Inventory

Tests for:
- /health returns templates_count field with correct value
- templates_count matches actual .jinja2 files on disk
- TemplateSelector resolves all 7 known operations
- TemplateSelector rejects empty and unknown operations
- HealthResponse model correctly validates templates_count
- LuaCodeGenerator renders non-empty code for every template
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, _templates_dir, _templates_count
from app.models import HealthResponse
from app.services.error_mapper import NormalizedValidationError
from app.services.lua_codegen import LuaCodeGenerator
from app.services.template_selector import TemplateSelector


KNOWN_OPERATIONS = list(TemplateSelector._OPERATION_TO_TEMPLATE.keys())
TEMPLATES_DIR = Path(_templates_dir)


# ---------------------------------------------------------------------------
# /health endpoint
# ---------------------------------------------------------------------------

class TestHealthTemplatesCount:
    def test_health_returns_templates_count_field(self, monkeypatch):
        """GET /health must include templates_count in the JSON body."""
        client = TestClient(app)

        async def fake_health():
            await asyncio.sleep(0)
            return True

        monkeypatch.setattr("app.main.ollama.health", fake_health)
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert "templates_count" in body, "templates_count missing from /health response"

    def test_health_templates_count_is_positive(self, monkeypatch):
        """templates_count must be greater than zero."""
        client = TestClient(app)

        async def fake_health():
            await asyncio.sleep(0)
            return True

        monkeypatch.setattr("app.main.ollama.health", fake_health)
        body = client.get("/health").json()
        assert body["templates_count"] > 0

    def test_health_templates_count_matches_disk(self, monkeypatch):
        """templates_count returned by /health must equal actual .jinja2 files."""
        client = TestClient(app)

        async def fake_health():
            await asyncio.sleep(0)
            return True

        monkeypatch.setattr("app.main.ollama.health", fake_health)
        body = client.get("/health").json()

        disk_count = len(list(TEMPLATES_DIR.glob("*.jinja2")))
        assert body["templates_count"] == disk_count

    def test_health_includes_model_name(self, monkeypatch):
        """GET /health must include a non-empty model field."""
        client = TestClient(app)

        async def fake_health():
            await asyncio.sleep(0)
            return True

        monkeypatch.setattr("app.main.ollama.health", fake_health)
        body = client.get("/health").json()
        assert body.get("model"), "model field missing or empty in /health response"


class TestModelSelectionEndpoints:
    def test_models_endpoint_returns_available_models(self, monkeypatch):
        """GET /models must return the active model and available model list."""
        client = TestClient(app)

        async def fake_list_models():
            await asyncio.sleep(0)
            return ["llama3.2:3b", "qwen2.5-coder:1.5b"]

        monkeypatch.setattr("app.main.ollama.list_models", fake_list_models)
        monkeypatch.setattr("app.main.ollama.model", "qwen2.5-coder:1.5b")

        response = client.get("/models")
        assert response.status_code == 200
        body = response.json()
        assert body["active_model"] == "qwen2.5-coder:1.5b"
        assert body["models"] == ["llama3.2:3b", "qwen2.5-coder:1.5b"]

    def test_model_select_switches_active_model(self, monkeypatch):
        """POST /models/select must update the active model when requested model exists."""
        client = TestClient(app)

        async def fake_list_models():
            await asyncio.sleep(0)
            return ["llama3.2:3b", "qwen2.5-coder:1.5b"]

        monkeypatch.setattr("app.main.ollama.list_models", fake_list_models)
        monkeypatch.setattr("app.main.ollama.model", "qwen2.5-coder:1.5b")

        response = client.post("/models/select", json={"model": "llama3.2:3b"})
        assert response.status_code == 200
        body = response.json()
        assert body["active_model"] == "llama3.2:3b"
        assert body["models"] == ["llama3.2:3b", "qwen2.5-coder:1.5b"]

    def test_model_select_rejects_unknown_model(self, monkeypatch):
        """POST /models/select must reject models not present in Ollama tags."""
        client = TestClient(app)

        async def fake_list_models():
            await asyncio.sleep(0)
            return ["llama3.2:3b", "qwen2.5-coder:1.5b"]

        monkeypatch.setattr("app.main.ollama.list_models", fake_list_models)

        response = client.post("/models/select", json={"model": "missing:model"})
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "model_not_found"
        assert detail["model"] == "missing:model"

    def test_health_returns_runtime_active_model(self, monkeypatch):
        """GET /health must expose the currently active runtime model after switching."""
        client = TestClient(app)

        async def fake_health():
            await asyncio.sleep(0)
            return True

        monkeypatch.setattr("app.main.ollama.health", fake_health)
        monkeypatch.setattr("app.main.ollama.model", "llama3.2:3b")

        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["model"] == "llama3.2:3b"


# ---------------------------------------------------------------------------
# HealthResponse Pydantic model
# ---------------------------------------------------------------------------

class TestHealthResponseModel:
    def test_health_response_accepts_templates_count(self):
        """HealthResponse must accept templates_count without error."""
        response = HealthResponse(
            status="ok",
            ollama="available",
            model="test-model",
            docker="available",
            templates_count=7,
        )
        assert response.templates_count == 7

    def test_health_response_templates_count_optional(self):
        """templates_count must be optional (defaults to None)."""
        response = HealthResponse(
            status="ok",
            ollama="available",
            model="test-model",
        )
        assert response.templates_count is None

    def test_module_level_templates_count_equals_7(self):
        """The pre-computed _templates_count in main must equal 7 (all templates present)."""
        assert _templates_count == 7


# ---------------------------------------------------------------------------
# TemplateSelector
# ---------------------------------------------------------------------------

class TestTemplateSelectorInventory:
    def test_all_known_operations_resolve(self):
        """Every operation in TemplateSelector._OPERATION_TO_TEMPLATE must resolve to an existing file."""
        selector = TemplateSelector(templates_dir=str(TEMPLATES_DIR))
        for op in KNOWN_OPERATIONS:
            path = selector.select_template(op)
            assert path.exists(), f"Template file missing for operation '{op}': {path}"

    def test_known_operations_count_equals_templates_on_disk(self):
        """Number of known operations must equal number of .jinja2 files."""
        disk_count = len(list(TEMPLATES_DIR.glob("*.jinja2")))
        assert len(KNOWN_OPERATIONS) == disk_count

    def test_unknown_operation_raises_normalized_error(self):
        """Requesting a completely unknown operation must raise NormalizedValidationError."""
        selector = TemplateSelector(templates_dir=str(TEMPLATES_DIR))
        with pytest.raises(NormalizedValidationError) as exc_info:
            selector.select_template("nonexistent_op")
        err = exc_info.value
        assert err.source == "template_selector"
        assert err.field == "operation"

    def test_empty_operation_raises_normalized_error(self):
        """Empty string as operation must raise NormalizedValidationError."""
        selector = TemplateSelector(templates_dir=str(TEMPLATES_DIR))
        with pytest.raises(NormalizedValidationError):
            selector.select_template("")

    def test_operation_names_match_template_filenames(self):
        """Each mapped template filename must start with its operation name."""
        for op, filename in TemplateSelector._OPERATION_TO_TEMPLATE.items():
            assert filename.startswith(op), (
                f"Template filename '{filename}' does not start with operation name '{op}'"
            )


# ---------------------------------------------------------------------------
# LuaCodeGenerator — renders all templates
# ---------------------------------------------------------------------------

_MINIMAL_PARAMS: dict[str, dict] = {
    "array_last": {"source": "wf.vars.items"},
    "math_increment": {"variable": "wf.vars.counter", "step": 1},
    "object_clean": {"source": "wf.vars.obj", "fields_to_remove": ["tmp"]},
    "array_filter": {"source": "wf.vars.items", "condition": "item.active == true"},
    "datetime_iso": {"date_field": "wf.vars.dateStr", "time_field": "wf.vars.timeStr"},
    "datetime_unix": {"source": "wf.vars.ts"},
    "ensure_array_field": {"source": "wf.vars.data", "field": "items"},
}


class TestLuaCodeGeneratorAllTemplates:
    def test_all_templates_render_non_empty_lua(self):
        """Every template must produce a non-empty Lua string for minimal valid params."""
        selector = TemplateSelector(templates_dir=str(TEMPLATES_DIR))
        codegen = LuaCodeGenerator(templates_dir=str(TEMPLATES_DIR))

        for op in KNOWN_OPERATIONS:
            template_path = selector.select_template(op)
            params = _MINIMAL_PARAMS[op]
            lua = codegen.generate_code(operation=op, params=params, template_path=template_path)
            assert lua.strip(), f"Rendered Lua for '{op}' is empty"
            assert "error" not in lua.lower() or "error(" in lua, (
                f"Unexpected error string in rendered Lua for '{op}'"
            )

    def test_array_last_lua_contains_source_path(self):
        """array_last template must embed the source expression in the rendered code."""
        selector = TemplateSelector(templates_dir=str(TEMPLATES_DIR))
        codegen = LuaCodeGenerator(templates_dir=str(TEMPLATES_DIR))
        template_path = selector.select_template("array_last")
        lua = codegen.generate_code(
            operation="array_last",
            params={"source": "wf.vars.emails"},
            template_path=template_path,
        )
        assert "wf.vars.emails" in lua

    def test_math_increment_lua_contains_step(self):
        """math_increment template must embed the step value in the rendered code."""
        selector = TemplateSelector(templates_dir=str(TEMPLATES_DIR))
        codegen = LuaCodeGenerator(templates_dir=str(TEMPLATES_DIR))
        template_path = selector.select_template("math_increment")
        lua = codegen.generate_code(
            operation="math_increment",
            params={"variable": "wf.vars.count", "step": 5},
            template_path=template_path,
        )
        assert "5" in lua
        assert "wf.vars.count" in lua
