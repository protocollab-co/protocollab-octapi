from __future__ import annotations

import logging
import math
from pathlib import Path
import re
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.services.error_mapper import NormalizedValidationError

logger = logging.getLogger(__name__)

# Allowed function prefixes for Call nodes in to_lua (security allow-list)
_ALLOWED_CALL_PREFIXES = (
    "tonumber", "tostring", "type",
    "pairs", "ipairs", "next",
    "string.", "table.", "math.",
    "select", "unpack",
)


def _is_allowed_call(func_name: str) -> bool:
    return any(
        func_name == prefix or func_name.startswith(prefix)
        for prefix in _ALLOWED_CALL_PREFIXES
    )


def _map_operator(op: str) -> str:
    if op == "!=":
        return "~="
    return op


def _func_node_name(func_node: Any) -> str:
    """Return a dotted name string for a Call's func node, or empty string."""
    node_type = type(func_node).__name__
    if node_type == "Name":
        return getattr(func_node, "name", "")
    if node_type == "Attribute":
        parent = _func_node_name(getattr(func_node, "obj"))
        attr = getattr(func_node, "attr", "")
        if parent:
            return f"{parent}.{attr}"
        return attr
    return ""


def to_lua(node: Any, strict: bool = False) -> str:
    """Transpile a protocollab/app.expression AST node to a Lua expression string.

    Parameters
    ----------
    node:
        Any AST node from app.expression.ast_nodes.
    strict:
        If True, raise NormalizedValidationError for unsupported nodes.
        If False (default), log a warning and return ``"nil"``.
    """
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
        return f"{to_lua(getattr(node, 'obj'), strict)}.{getattr(node, 'attr')}"

    if node_type == "Subscript":
        return f"{to_lua(getattr(node, 'obj'), strict)}[{to_lua(getattr(node, 'index'), strict)}]"

    if node_type == "InOp":
        left = to_lua(getattr(node, "left"), strict)
        right = to_lua(getattr(node, "right"), strict)
        # Inline membership helper to keep expression pure and sandbox-safe.
        return (
            "((function(__l,__r) "
            "if type(__r) == 'table' then for _,__v in ipairs(__r) do if __v == __l then return true end end end "
            "return false end)("
            f"{left}, {right}))"
        )

    if node_type == "UnaryOp":
        op = getattr(node, "op")
        operand = to_lua(getattr(node, "operand"), strict)
        if op == "#":
            return f"(#{operand})"
        lua_op = _map_operator(op)
        return f"({lua_op} {operand})"

    if node_type == "BinOp":
        op = _map_operator(getattr(node, "op"))
        left = to_lua(getattr(node, "left"), strict)
        right = to_lua(getattr(node, "right"), strict)
        return f"({left} {op} {right})"

    if node_type == "Ternary":
        value_if_true = to_lua(getattr(node, "value_if_true"), strict)
        condition = to_lua(getattr(node, "condition"), strict)
        value_if_false = to_lua(getattr(node, "value_if_false"), strict)
        return f"(({condition}) and ({value_if_true}) or ({value_if_false}))"

    if node_type == "Call":
        func_node = getattr(node, "func")
        func_name = _func_node_name(func_node)
        args = getattr(node, "args", ())
        args_lua = ", ".join(to_lua(a, strict) for a in args)
        if func_name and _is_allowed_call(func_name):
            return f"{func_name}({args_lua})"
        # Disallowed call
        msg = f"Call to '{func_name or '?'}' is not allowed in Lua transpile"
        if strict:
            raise NormalizedValidationError(
                field="parameters.condition",
                message=msg,
                expected="allowed call: tonumber/tostring/type/string.*/table.*/math.*",
                got=func_name or "unknown",
                hint="Use only safe built-in Lua functions.",
                source="template_selector",
            )
        logger.warning("to_lua: %s — returning nil", msg)
        return "nil"

    if node_type in {"List", "ListLiteral"}:
        elements = getattr(node, "elements", ())
        elems_lua = ", ".join(to_lua(e, strict) for e in elements)
        return f"{{ {elems_lua} }}"

    if node_type == "DictLiteral":
        keys = getattr(node, "keys", ())
        values = getattr(node, "values", ())
        items_lua = []
        for k, v in zip(keys, values):
            k_lua = to_lua(k, strict)
            v_lua = to_lua(v, strict)
            items_lua.append(f"[{k_lua}] = {v_lua}")
        return "{ " + ", ".join(items_lua) + " }"

    if node_type == "Dict":
        pairs = getattr(node, "pairs", ())
        items_lua = []
        for k, v in pairs:
            key_type = type(k).__name__
            if key_type != "Literal":
                if strict:
                    raise NormalizedValidationError(
                        field="parameters.condition",
                        message="Dict keys must be string or number literals for Lua transpile",
                        expected="literal string or number key",
                        got=key_type,
                        hint="Use dictionary keys like {'name': value} or {1: value}.",
                        source="template_selector",
                    )
                logger.warning("to_lua: dict key node '%s' is not a Literal — returning nil", key_type)
                return "nil"

            key_value = getattr(k, "value", None)
            if not isinstance(key_value, (str, int, float)):
                if strict:
                    raise NormalizedValidationError(
                        field="parameters.condition",
                        message="Dict keys must be string or number literals for Lua transpile",
                        expected="literal string or number key",
                        got=str(type(key_value).__name__),
                        hint="Use dictionary keys like {'name': value} or {1: value}.",
                        source="template_selector",
                    )
                logger.warning("to_lua: dict key literal type '%s' unsupported — returning nil", type(key_value).__name__)
                return "nil"

            k_lua = to_lua(k, strict)
            v_lua = to_lua(v, strict)
            items_lua.append(f"[{k_lua}] = {v_lua}")
        return "{ " + ", ".join(items_lua) + " }"

    # Fallback for Lambda, Compare, Tuple, Slice, etc.
    if strict:
        raise NormalizedValidationError(
            field="parameters.condition",
            message=f"Unsupported AST node: {node_type}, please simplify expression",
            expected="supported AST node (Literal/Name/Attribute/Subscript/UnaryOp/BinOp/Ternary/InOp/ListLiteral/DictLiteral)",
            got=node_type,
            hint="Simplify the expression to use only supported constructs.",
            source="template_selector",
        )
    logger.warning("to_lua: unsupported AST node type '%s' — returning nil", node_type)
    return "nil"


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
    _BARE_PATH_PATTERN = re.compile(
        r'^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[0-9]+\]|\["[A-Za-z0-9_\- ]+"\])*$',
    )
    _DOLLAR_NAME_PATTERN = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
    _LENGTH_CALL_PATTERN = re.compile(r"\b(?:length|len)\s*\(([^\)]*)\)")
    _ISINSTANCE_LIST_PATTERN = re.compile(r"\bisinstance\s*\(([^,]+),\s*list\s*\)")
    _AT_PLACEHOLDER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])@(?![A-Za-z0-9_])")
    _NOT_DASH_PATTERN = re.compile(r"\bnot\s*-\s*")

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
        value = self._normalize_lua_expression(value)
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

    def _normalize_lua_expression(self, value: str) -> str:
        """Normalize common safe model outputs to wf.vars-prefixed expressions.

        Example: ``ZCDF_PACKAGES.items`` -> ``wf.vars.ZCDF_PACKAGES.items``
        """
        text = value.strip()
        if self._LUA_EXPR_PATTERN.fullmatch(text):
            return text
        if self._BARE_PATH_PATTERN.fullmatch(text):
            return f"wf.vars.{text}"
        return text

    def _normalize_condition_expression(self, value: str) -> str:
        """Normalize common model output to protocollab-compatible syntax."""
        text = value.strip()
        # YAML list coercion artifacts: "not - expr" -> "not expr"
        text = self._NOT_DASH_PATTERN.sub("not ", text)
        # $item.attr -> item.attr
        text = self._DOLLAR_NAME_PATTERN.sub(r"\1", text)
        # @ -> item
        text = self._AT_PLACEHOLDER_PATTERN.sub("item", text)
        # C-style logical operators -> protocollab operators
        text = text.replace("||", " or ").replace("&&", " and ")
        # Lua not-equal operator -> expression parser form
        text = text.replace("~=", "!=")
        # Upper-case logical operators -> lower-case parser form
        text = re.sub(r"\bOR\b", "or", text)
        text = re.sub(r"\bAND\b", "and", text)
        text = re.sub(r"\bNOT\b", "not", text)
        # length(x) / len(x) -> (x).length
        text = self._LENGTH_CALL_PATTERN.sub(r"(\1).length", text)
        # isinstance(x, list) is not part of expression grammar; degrade to null-check.
        text = self._ISINSTANCE_LIST_PATTERN.sub(r"(\1) != null", text)
        return text

    def _coerce_condition(self, params: dict[str, Any]) -> str:
        value = params.get("condition")
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list):
            parts = [str(part).strip() for part in value if str(part).strip()]
            if parts:
                return " and ".join(parts)
        raise NormalizedValidationError(
            field="parameters.condition",
            message="Missing or invalid required parameter: condition",
            expected="non-empty string",
            got=str(value),
            hint="Provide condition as a single expression string.",
            source="template_selector",
        )

    @staticmethod
    def _require_number(params: dict[str, Any], key: str) -> float | int:
        value = params.get(key)
        # Accept string representations of numbers
        if isinstance(value, str):
            try:
                value = float(value)
                if value == int(value):
                    value = int(value)
            except ValueError:
                value = None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise NormalizedValidationError(
                field=f"parameters.{key}",
                message=f"Missing or invalid required numeric parameter: {key}",
                expected="number",
                got=str(params.get(key)),
                hint="Provide numeric value for this parameter.",
                source="template_selector",
            )
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            raise NormalizedValidationError(
                field=f"parameters.{key}",
                message=f"Parameter {key} must be a finite number (not NaN or Inf)",
                expected="finite number",
                got=str(value),
                hint="Provide a finite numeric value.",
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
            condition = self._coerce_condition(clean_params)
            condition = self._normalize_condition_expression(condition)
            try:
                from app.expression.parser import parse_expr
            except Exception as exc:
                raise NormalizedValidationError(
                    field="parameters.condition",
                    message=f"Expression parser unavailable: {exc}",
                    expected="available app.expression parser",
                    got="missing parser",
                    hint="Ensure app/expression/ module is present.",
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
