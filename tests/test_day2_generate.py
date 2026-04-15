import asyncio

from fastapi.testclient import TestClient

from app.main import app


def test_ask_completes_after_clarification(monkeypatch):
    client = TestClient(app)
    responses = [
        '{"operation":"unknown","parameters":{"source":"wf.vars.emails"}}',
        "operation: array_last\nparameters:\n  source: wf.vars.emails\n",
    ]

    async def fake_generate_yaml_text(prompt, context, system_prompt):
        await asyncio.sleep(0)
        return responses.pop(0)

    monkeypatch.setattr("app.main.ollama.generate_yaml_text", fake_generate_yaml_text)

    first = client.post("/generate", json={"prompt": "получи последний email"})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["is_complete"] is False
    assert first_body["lua_code"].startswith("-- Diagnostic Lua fallback")

    second = client.post(
        "/ask",
        json={"session_id": first_body["session_id"], "question": "используй operation array_last"},
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["is_complete"] is True
    assert second_body["attempts"] == 2
    assert second_body["yaml"]["operation"] == "array_last"


def test_ask_uses_yaml_prompt(monkeypatch):
    client = TestClient(app)
    captured_prompts = []
    responses = [
        '{"operation":"unknown","parameters":{"source":"wf.vars.emails"}}',
        "operation: array_last\nparameters:\n  source: wf.vars.emails\n",
    ]

    async def fake_generate_yaml_text(prompt, context, system_prompt):
        await asyncio.sleep(0)
        captured_prompts.append(system_prompt)
        return responses.pop(0)

    monkeypatch.setattr("app.main.ollama.generate_yaml_text", fake_generate_yaml_text)

    first = client.post("/generate", json={"prompt": "получи последний email"})
    assert first.status_code == 200

    second = client.post(
        "/ask",
        json={"session_id": first.json()["session_id"], "question": "используй operation array_last"},
    )
    assert second.status_code == 200
    assert "Return only JSON" in captured_prompts[0]
    assert "Return only YAML" in captured_prompts[1]


def test_ask_returns_controlled_error_when_attempts_exhausted(monkeypatch):
    client = TestClient(app)

    async def fake_generate_yaml_text(prompt, context, system_prompt):
        await asyncio.sleep(0)
        return "operation: unknown\nparameters:\n  source: wf.vars.emails\n"

    monkeypatch.setattr("app.main.ollama.generate_yaml_text", fake_generate_yaml_text)

    first = client.post("/generate", json={"prompt": "bad"})
    assert first.status_code == 200
    session_id = first.json()["session_id"]

    second = client.post(
        "/ask",
        json={"session_id": session_id, "question": "уточнение 1", "auto_correction": True},
    )
    assert second.status_code == 200
    assert second.json()["attempts"] == 2

    third = client.post(
        "/ask",
        json={"session_id": session_id, "question": "уточнение 2", "auto_correction": True},
    )
    assert third.status_code == 409
    detail = third.json()["detail"]
    assert detail["code"] == "attempt_limit_reached"
    assert detail["attempts"] == 3


def test_ask_fixes_expression_error_within_three_attempts(monkeypatch):
    client = TestClient(app)
    responses = [
        (
            "operation: array_filter\n"
            "parameters:\n"
            "  source: wf.vars.parsedCsv\n"
            "  condition: item.Discount ~= ~= nil\n"
        ),
        (
            "operation: array_filter\n"
            "parameters:\n"
            "  source: wf.vars.parsedCsv\n"
            "  condition: item.Discount ~= nil\n"
        ),
    ]

    async def fake_generate_yaml_text(prompt, context, system_prompt):
        await asyncio.sleep(0)
        return responses.pop(0)

    def fake_validate_expr(expr):
        if "~= ~=" in expr:
            raise ValueError("duplicated operator")

    monkeypatch.setattr("app.main.ollama.generate_yaml_text", fake_generate_yaml_text)
    monkeypatch.setattr("app.services.yaml_pipeline.YamlValidationPipeline._resolve_expression_validator", lambda self: fake_validate_expr)

    first = client.post("/generate", json={"prompt": "отфильтруй записи с Discount"})
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["is_complete"] is False
    assert first_body["feedback"][0]["source"] == "expression"
    assert first_body["lua_code"].startswith("-- Diagnostic Lua fallback")

    second = client.post(
        "/ask",
        json={"session_id": first_body["session_id"], "question": "исправь condition без двойного оператора"},
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["is_complete"] is True
    assert second_body["attempts"] == 2
    assert second_body["yaml"]["operation"] == "array_filter"
