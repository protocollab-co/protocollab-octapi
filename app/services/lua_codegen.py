from __future__ import annotations

from pathlib import Path
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
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
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
        context: dict[str, Any] = {"operation": operation, "params": params}

        if operation == "array_filter":
            condition = self._require_string(params, "condition")
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
