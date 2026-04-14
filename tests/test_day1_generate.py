import asyncio

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_ok_when_ollama_available(monkeypatch):
    client = TestClient(app)

    async def fake_health():
        await asyncio.sleep(0)
        return True

    monkeypatch.setattr("app.main.ollama.health", fake_health)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"


def test_generate_success(monkeypatch):
    client = TestClient(app)

    async def fake_generate_yaml_text(prompt, context, system_prompt):
        await asyncio.sleep(0)
        return "operation: array_last\nparameters:\n  source: wf.vars.emails\n"

    monkeypatch.setattr("app.main.ollama.generate_yaml_text", fake_generate_yaml_text)
    response = client.post("/generate", json={"prompt": "получи последний email"})
    assert response.status_code == 200
    body = response.json()
    assert body["is_complete"] is True
    assert body["session_id"]
    assert body["yaml"]["operation"] == "array_last"


def test_generate_schema_error(monkeypatch):
    client = TestClient(app)

    async def fake_generate_yaml_text(prompt, context, system_prompt):
        await asyncio.sleep(0)
        return "operation: unknown\nparameters:\n  source: wf.vars.emails\n"

    monkeypatch.setattr("app.main.ollama.generate_yaml_text", fake_generate_yaml_text)
    response = client.post("/generate", json={"prompt": "bad"})
    assert response.status_code == 200
    body = response.json()
    assert body["is_complete"] is False
    assert body["feedback"][0]["source"] == "schema"
    assert body["lua_code"].startswith("-- Diagnostic Lua fallback")
    assert body["lua_code"].rstrip().endswith("return nil")


def test_generate_expression_error(monkeypatch):
    client = TestClient(app)

    async def fake_generate_yaml_text(prompt, context, system_prompt):
        await asyncio.sleep(0)
        return (
            "operation: array_filter\n"
            "parameters:\n"
            "  source: wf.vars.parsedCsv\n"
            "  condition: item.Discount ~= ~= nil\n"
        )

    def fake_validate_expr(expr):
        raise ValueError("invalid expression")

    monkeypatch.setattr("app.services.yaml_pipeline.YamlValidationPipeline._resolve_expression_validator", lambda self: fake_validate_expr)
    monkeypatch.setattr("app.main.ollama.generate_yaml_text", fake_generate_yaml_text)
    response = client.post("/generate", json={"prompt": "bad expr"})
    assert response.status_code == 200
    body = response.json()
    assert body["is_complete"] is False
    assert body["feedback"][0]["source"] == "expression"
    assert body["lua_code"].startswith("-- Diagnostic Lua fallback")


def test_generate_normalizes_placeholder_scalar(monkeypatch):
    client = TestClient(app)

    async def fake_generate_yaml_text(prompt, context, system_prompt):
        await asyncio.sleep(0)
        return (
            "operation: datetime_unix\n"
            "parameters:\n"
            "  source: {{wf.vars.timestamp}}\n"
        )

    monkeypatch.setattr("app.main.ollama.generate_yaml_text", fake_generate_yaml_text)
    response = client.post("/generate", json={"prompt": "конвертируй timestamp в unix"})
    assert response.status_code == 200
    body = response.json()
    assert body["is_complete"] is True
    assert body["yaml"]["operation"] == "datetime_unix"
    assert body["yaml"]["parameters"]["source"] == "wf.vars.timestamp"


def test_generate_normalizes_array_filter_condition_rule_list(monkeypatch):
    client = TestClient(app)

    async def fake_generate_yaml_text(prompt, context, system_prompt):
        await asyncio.sleep(0)
        return (
            "operation: array_filter\n"
            "parameters:\n"
            "  source: wf.vars.result\n"
            "  condition:\n"
            "    - field: Discount\n"
            "      operator: not_null\n"
            "    - field: Markdown\n"
            "      operator: not_null\n"
        )

    monkeypatch.setattr("app.main.ollama.generate_yaml_text", fake_generate_yaml_text)
    monkeypatch.setattr(
        "app.services.yaml_pipeline.YamlValidationPipeline._resolve_expression_validator",
        lambda self: (lambda expr: None),
    )

    response = client.post("/generate", json={"prompt": "отфильтруй записи с Discount или Markdown"})
    assert response.status_code == 200
    body = response.json()
    assert body["is_complete"] is True
    assert body["yaml"]["operation"] == "array_filter"
    assert body["yaml"]["parameters"]["condition"] == "item.Discount != nil or item.Markdown != nil"
