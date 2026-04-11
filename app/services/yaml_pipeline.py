from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import logging
import re
from tempfile import NamedTemporaryFile

from app.services.error_mapper import NormalizedValidationError

logger = logging.getLogger(__name__)


class YamlValidationPipeline:
    def __init__(self, schema_path: str) -> None:
        self.schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        self._schema_validator = self._build_schema_validator(self.schema)

    def parse_and_validate(self, raw_text: str) -> dict[str, Any]:
        yaml_text = self._extract_yaml(raw_text)
        parsed = self._load_yaml(yaml_text)
        self._validate_schema(parsed)
        self._validate_expression_if_needed(parsed)
        return parsed

    def _extract_yaml(self, raw_text: str) -> str:
        fenced = re.search(r"```yaml\s*(.*?)```", raw_text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
        generic_fence = re.search(r"```\s*(.*?)```", raw_text, flags=re.DOTALL)
        if generic_fence:
            return generic_fence.group(1).strip()
        return raw_text.strip()

    def _load_yaml(self, yaml_text: str) -> dict[str, Any]:
        try:
            from yaml_serializer import SerializerSession  # type: ignore

            logger.info("[YAML_PARSER] Using protocollab yaml_serializer.SerializerSession")
            with NamedTemporaryFile("w", delete=False, suffix=".yaml", encoding="utf-8") as tmp:
                tmp.write(yaml_text)
                tmp_path = tmp.name
            session = SerializerSession(
                {
                    "max_file_size": 10_000,
                    "max_struct_depth": 10,
                    "max_include_depth": 10,
                    "max_imports": 0,
                }
            )
            data = session.load(tmp_path)
            if not isinstance(data, dict):
                raise NormalizedValidationError(
                    field="yaml",
                    message="Top-level YAML value must be an object.",
                    expected="mapping",
                    got=type(data).__name__,
                    hint="Return YAML with top-level keys operation and parameters.",
                    source="yaml",
                )
            return data
        except ModuleNotFoundError:
            import yaml

            logger.warning("[YAML_PARSER] protocollab not installed; using PyYAML fallback")
            data = yaml.safe_load(yaml_text)
            if not isinstance(data, dict):
                raise NormalizedValidationError(
                    field="yaml",
                    message="Top-level YAML value must be an object.",
                    expected="mapping",
                    got=type(data).__name__,
                    hint="Return YAML with top-level keys operation and parameters.",
                    source="yaml",
                )
            return data
        except NormalizedValidationError:
            raise
        except Exception as exc:
            logger.exception("[YAML_PARSER] Failed to parse YAML")
            raise NormalizedValidationError(
                field="yaml",
                message=f"YAML parsing failed: {exc}",
                expected="valid YAML",
                got="invalid YAML",
                hint="Return only YAML without explanations.",
                source="yaml",
            ) from exc

    def _build_schema_validator(self, schema: dict[str, Any]) -> Any:
        try:
            from jsonschema_validator import ValidatorFactory  # type: ignore

            logger.info("[SCHEMA_VALIDATION] Using protocollab.jsonschema_validator")
            return ValidatorFactory.create(backend="auto")
        except Exception:
            from jsonschema import Draft202012Validator

            logger.info("[SCHEMA_VALIDATION] Falling back to jsonschema Draft202012Validator")
            return Draft202012Validator(schema)

    def _validate_schema(self, parsed: dict[str, Any]) -> None:
        try:
            if hasattr(self._schema_validator, "validate") and "jsonschema_validator" in type(self._schema_validator).__module__:
                errors = self._schema_validator.validate(self.schema, parsed)
                if errors:
                    first = errors[0]
                    field_path = ".".join(first.path) if getattr(first, "path", None) else "operation"
                    raise NormalizedValidationError(
                        field=field_path,
                        message=getattr(first, "message", "Schema validation failed"),
                        expected="schema-compliant value",
                        got="invalid",
                        hint="Check required fields and allowed operation values.",
                        source="schema",
                    )
                return

            errors = list(self._schema_validator.iter_errors(parsed))
            if errors:
                first = errors[0]
                field_path = ".".join([str(p) for p in first.absolute_path]) or "operation"
                raise NormalizedValidationError(
                    field=field_path,
                    message=first.message,
                    expected="schema-compliant value",
                    got="invalid",
                    hint="Check required fields and allowed operation values.",
                    source="schema",
                )
        except NormalizedValidationError:
            raise
        except Exception as exc:
            message = str(exc)
            field = "operation" if "operation" in message else "parameters"
            raise NormalizedValidationError(
                field=field,
                message=message,
                expected="schema-compliant value",
                got="invalid",
                hint="Check required fields and allowed operation values.",
                source="schema",
            ) from exc

    def _validate_expression_if_needed(self, parsed: dict[str, Any]) -> None:
        if parsed.get("operation") != "array_filter":
            return

        parameters = parsed.get("parameters", {})
        condition = parameters.get("condition")
        if not isinstance(condition, str) or not condition.strip():
            raise NormalizedValidationError(
                field="parameters.condition",
                message="condition is required for array_filter",
                expected="non-empty string",
                got="missing",
                hint="Provide a condition like item.Discount ~= nil.",
                source="expression",
            )

        validator = self._resolve_expression_validator()
        try:
            validator(condition)
        except Exception as exc:
            raise NormalizedValidationError(
                field="parameters.condition",
                message=f"Invalid condition expression: {exc}",
                expected="valid protocollab expression",
                got=condition,
                hint="Use operators supported by protocollab.expression.",
                source="expression",
            ) from exc

    @staticmethod
    def _resolve_expression_validator():
        try:
            from protocollab.expression import validate_expr  # type: ignore

            logger.info("[EXPRESSION_VALIDATION] Using protocollab.expression.validate_expr")
            return validate_expr
        except Exception:
            try:
                from protocollab.expression.validator import validate_expr  # type: ignore

                logger.info("[EXPRESSION_VALIDATION] Using protocollab.expression.validator.validate_expr")
                return validate_expr
            except Exception:
                logger.warning("[EXPRESSION_VALIDATION] protocollab not installed; using minimal fallback")

                def _fallback_validate_expr(expr: str) -> None:
                    # Minimal sanity check for Day 1 local execution when protocollab is unavailable.
                    if "~= ~= " in expr or "== ==" in expr:
                        raise ValueError("unsupported duplicated operator sequence")
                    if expr.count("(") != expr.count(")"):
                        raise ValueError("unbalanced parentheses")

                return _fallback_validate_expr
