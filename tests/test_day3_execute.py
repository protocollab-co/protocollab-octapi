from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models import ExecutionResult
from app.services.error_mapper import NormalizedValidationError
from app.services.lua_codegen import to_lua
from app.services.template_selector import TemplateSelector
from app.expression.ast_nodes import Call, Dict, List, Literal as ExprLiteral, Name as ExprName


class Literal:
    def __init__(self, value):
        self.value = value


class Name:
    def __init__(self, name: str):
        self.name = name


class Attribute:
    def __init__(self, obj, attr: str):
        self.obj = obj
        self.attr = attr


class BinOp:
    def __init__(self, left, op: str, right):
        self.left = left
        self.op = op
        self.right = right


def test_template_selector_unknown_operation():
    selector = TemplateSelector(templates_dir="templates/octapi")

    try:
        selector.select_template("unknown")
        assert False, "Expected NormalizedValidationError"
    except NormalizedValidationError as exc:
        assert exc.source == "template_selector"
        assert exc.field == "operation"


def test_to_lua_binop_not_equal_mapping():
    ast = BinOp(Attribute(Name("item"), "Discount"), "!=", Literal(None))
    lua_expr = to_lua(ast)
    assert lua_expr == "(item.Discount ~= nil)"


def test_to_lua_escapes_control_chars_in_string_literal():
    ast = Literal('line1\n"quoted"\tline2\\tail')
    lua_expr = to_lua(ast)
    assert lua_expr == '"line1\\n\\"quoted\\"\\tline2\\\\tail"'


def test_to_lua_allows_safe_call_tonumber():
    ast = Call(func=ExprName("tonumber"), args=(ExprLiteral("5"),))
    lua_expr = to_lua(ast)
    assert lua_expr == 'tonumber("5")'


def test_to_lua_supports_nested_list_dict_tables():
    ast = Dict(
        pairs=(
            (ExprLiteral("outer"), List(elements=(ExprLiteral(1), ExprLiteral(2)))),
            (ExprLiteral(3), Dict(pairs=((ExprLiteral("x"), ExprLiteral(True)),))),
        )
    )
    lua_expr = to_lua(ast, strict=True)
    assert lua_expr == '{ ["outer"] = { 1, 2 }, [3] = { ["x"] = true } }'


def test_to_lua_rejects_unsupported_dict_key_in_strict_mode():
    ast = Dict(pairs=((ExprName("dynamic_key"), ExprLiteral("value")),))
    try:
        to_lua(ast, strict=True)
        assert False, "Expected NormalizedValidationError"
    except NormalizedValidationError as exc:
        assert "Dict keys must be string or number literals" in exc.message


def test_execute_with_inline_yaml_success(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr("app.main.lua_validator.validate_syntax", lambda code: None)
    monkeypatch.setattr(
        "app.main.sandbox_executor.execute",
        lambda lua_code, context: ExecutionResult(status="success", stdout="ok\n", stderr="", exit_code=0),
    )

    response = client.post(
        "/execute",
        json={
            "yaml": {
                "operation": "array_last",
                "parameters": {"source": "wf.vars.emails"},
            },
            "context": {"wf": {"vars": {"emails": ["a", "b"]}}},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["operation"] == "array_last"
    assert body["execution_result"]["status"] == "success"
    assert "wf.vars.emails" in body["lua_code"]


def test_execute_unknown_operation_returns_controlled_error(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr("app.main.lua_validator.validate_syntax", lambda code: None)

    response = client.post(
        "/execute",
        json={
            "yaml": {
                "operation": "unknown_op",
                "parameters": {"source": "wf.vars.emails"},
            }
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["source"] == "template_selector"


def test_execute_rejects_session_id_and_yaml_together(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr("app.main.lua_validator.validate_syntax", lambda code: None)
    monkeypatch.setattr(
        "app.main.sandbox_executor.execute",
        lambda lua_code, context: ExecutionResult(status="success", stdout="ok\n", stderr="", exit_code=0),
    )

    response = client.post(
        "/execute",
        json={
            "session_id": "abc123",
            "yaml": {
                "operation": "array_last",
                "parameters": {"source": "wf.vars.emails"},
            },
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "invalid_execute_payload"


def test_execute_rejects_unsafe_lua_expression(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr("app.main.lua_validator.validate_syntax", lambda code: None)

    response = client.post(
        "/execute",
        json={
            "yaml": {
                "operation": "array_last",
                "parameters": {"source": 'wf.vars.emails; os.execute("id")'},
            }
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["source"] == "template_selector"
    assert detail["field"] == "parameters.source"


def test_execute_luac_error_mapped(monkeypatch):
    client = TestClient(app)

    def _raise_luac(_code: str):
        raise NormalizedValidationError(
            field="lua",
            message="luac syntax check failed",
            expected="valid Lua syntax",
            got="syntax error",
            hint="Fix script",
            source="lua_syntax",
        )

    monkeypatch.setattr("app.main.lua_validator.validate_syntax", _raise_luac)

    response = client.post(
        "/execute",
        json={
            "yaml": {
                "operation": "array_last",
                "parameters": {"source": "wf.vars.emails"},
            }
        },
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["source"] == "lua_syntax"


def test_all_day3_templates_exist():
    base = Path("templates/octapi")
    names = {
        "array_last.lua.jinja2",
        "math_increment.lua.jinja2",
        "object_clean.lua.jinja2",
        "array_filter.lua.jinja2",
        "datetime_iso.lua.jinja2",
        "datetime_unix.lua.jinja2",
        "ensure_array_field.lua.jinja2",
    }
    assert names.issubset({item.name for item in base.iterdir() if item.is_file()})
