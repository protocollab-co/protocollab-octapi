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
