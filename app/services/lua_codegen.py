from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.services.error_mapper import NormalizedValidationError


def _map_operator(op: str) -> str:
    if op == "!=":
        return "~="
    return op


def to_lua(node: Any) -> str:
    node_type = type(node).__name__

    if node_type == "Literal":
        value = getattr(node, "value", None)
        if value is None:
            return "nil"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            escaped = (
                value.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t")
            )
            return f'"{escaped}"'
        return str(value)

    if node_type == "Name":
        return getattr(node, "name")

    if node_type == "Attribute":
        return f"{to_lua(getattr(node, 'obj'))}.{getattr(node, 'attr')}"

    if node_type == "Subscript":
        return f"{to_lua(getattr(node, 'obj'))}[{to_lua(getattr(node, 'index'))}]"

    if node_type == "UnaryOp":
        op = _map_operator(getattr(node, "op"))
        return f"({op} {to_lua(getattr(node, 'operand'))})"

    if node_type == "BinOp":
        op = _map_operator(getattr(node, "op"))
        left = to_lua(getattr(node, "left"))
        right = to_lua(getattr(node, "right"))
        return f"({left} {op} {right})"

    if node_type == "Ternary":
        value_if_true = to_lua(getattr(node, "value_if_true"))
        condition = to_lua(getattr(node, "condition"))
        value_if_false = to_lua(getattr(node, "value_if_false"))
        return f"(({condition}) and ({value_if_true}) or ({value_if_false}))"

    raise NormalizedValidationError(
        field="parameters.condition",
        message=f"Unsupported AST node for Lua transpile: {node_type}",
        expected="supported protocollab AST node",
        got=node_type,
        hint="Update to_lua mapping for this node type.",
        source="template_selector",
    )


class LuaCodeGenerator:
    def __init__(self, templates_dir: str) -> None:
        self.templates_dir = Path(templates_dir)
        self._env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._env.filters["lua_string"] = self._escape_lua_string

    _LUA_EXPR_PATTERN = re.compile(
        r'^(?:wf\.vars|item)(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[0-9]+\]|\["[A-Za-z0-9_\- ]+"\])*$',
    )

    @staticmethod
    def _escape_lua_string(value: Any) -> str:
        text = str(value)
        return (
            text.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )

    def _require_lua_expression(self, params: dict[str, Any], key: str) -> str:
        value = self._require_string(params, key)
        if not self._LUA_EXPR_PATTERN.fullmatch(value):
            raise NormalizedValidationError(
                field=f"parameters.{key}",
                message=f"Unsafe or invalid Lua expression for parameter: {key}",
                expected='expression like wf.vars.field, wf.vars.obj["key"], or item.attr',
                got=value,
                hint="Use only wf.vars or item-based field access expressions.",
                source="template_selector",
            )
        return value

    @staticmethod
    def _require_number(params: dict[str, Any], key: str) -> float | int:
        value = params.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise NormalizedValidationError(
                field=f"parameters.{key}",
                message=f"Missing or invalid required numeric parameter: {key}",
                expected="number",
                got=str(value),
                hint="Provide numeric value for this parameter.",
                source="template_selector",
            )
        return value

    def _sanitize_params(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        clean = dict(params)

        if operation in {"array_filter", "array_last", "datetime_unix", "ensure_array_field", "object_clean"}:
            clean["source"] = self._require_lua_expression(clean, "source")

        if operation == "math_increment":
            clean["variable"] = self._require_lua_expression(clean, "variable")
            clean["step"] = self._require_number(clean, "step")

        if operation == "datetime_iso":
            clean["date_field"] = self._require_lua_expression(clean, "date_field")
            clean["time_field"] = self._require_lua_expression(clean, "time_field")

        if operation == "ensure_array_field":
            clean["field"] = self._require_string(clean, "field")

        if operation == "object_clean":
            fields = clean.get("fields_to_remove")
            if not isinstance(fields, list) or any(not isinstance(item, str) for item in fields):
                raise NormalizedValidationError(
                    field="parameters.fields_to_remove",
                    message="Missing or invalid required parameter: fields_to_remove",
                    expected="list of strings",
                    got=str(fields),
                    hint="Provide fields_to_remove as an array of string field names.",
                    source="template_selector",
                )

        return clean

    @staticmethod
    def _require_string(params: dict[str, Any], key: str) -> str:
        value = params.get(key)
        if not isinstance(value, str) or not value.strip():
            raise NormalizedValidationError(
                field=f"parameters.{key}",
                message=f"Missing or invalid required parameter: {key}",
                expected="non-empty string",
                got=str(value),
                hint="Provide all required operation parameters.",
                source="template_selector",
            )
        return value

    def _build_render_context(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        clean_params = self._sanitize_params(operation=operation, params=params)
        context: dict[str, Any] = {"operation": operation, "params": clean_params}

        if operation == "array_filter":
            condition = self._require_string(clean_params, "condition")
            try:
                from protocollab.expression import parse_expr  # type: ignore
            except Exception as exc:
                raise NormalizedValidationError(
                    field="parameters.condition",
                    message=f"protocollab.expression.parse_expr unavailable: {exc}",
                    expected="available protocollab expression parser",
                    got="missing parser",
                    hint="Install protocollab package and retry.",
                    source="template_selector",
                ) from exc

            try:
                ast = parse_expr(condition)
                context["condition_lua"] = to_lua(ast)
            except NormalizedValidationError:
                raise
            except Exception as exc:
                raise NormalizedValidationError(
                    field="parameters.condition",
                    message=f"Failed to transpile condition to Lua: {exc}",
                    expected="valid protocollab expression",
                    got=condition,
                    hint="Fix expression syntax/operators for protocollab parser.",
                    source="template_selector",
                ) from exc

        return context

    def generate_code(self, operation: str, params: dict[str, Any], template_path: Path) -> str:
        if not template_path.exists():
            raise NormalizedValidationError(
                field="operation",
                message=f"Template path does not exist: {template_path}",
                expected="existing template file",
                got=str(template_path),
                hint="Check template selector mapping.",
                source="template_selector",
            )

        render_context = self._build_render_context(operation=operation, params=params)
        try:
            template = self._env.get_template(template_path.name)
            return template.render(**render_context).strip() + "\n"
        except NormalizedValidationError:
            raise
        except Exception as exc:
            raise NormalizedValidationError(
                field="operation",
                message=f"Template rendering failed: {exc}",
                expected="renderable template and valid parameters",
                got=operation,
                hint="Review template placeholders and operation parameters.",
                source="template_selector",
            ) from exc
