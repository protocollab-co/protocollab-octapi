from __future__ import annotations

from pathlib import Path

from app.services.error_mapper import NormalizedValidationError


class TemplateSelector:
    _OPERATION_TO_TEMPLATE: dict[str, str] = {
        "array_last": "array_last.lua.jinja2",
        "math_increment": "math_increment.lua.jinja2",
        "object_clean": "object_clean.lua.jinja2",
        "array_filter": "array_filter.lua.jinja2",
        "datetime_iso": "datetime_iso.lua.jinja2",
        "datetime_unix": "datetime_unix.lua.jinja2",
        "ensure_array_field": "ensure_array_field.lua.jinja2",
    }

    def __init__(self, templates_dir: str) -> None:
        self.templates_dir = Path(templates_dir)

    def select_template(self, operation: str) -> Path:
        template_name = self._OPERATION_TO_TEMPLATE.get(operation)
        if not template_name:
            raise NormalizedValidationError(
                field="operation",
                message=f"Unknown operation for template selector: {operation}",
                expected="one of supported operations",
                got=operation,
                hint="Use one of schema-supported operation values.",
                source="template_selector",
            )

        template_path = self.templates_dir / template_name
        if not template_path.exists():
            raise NormalizedValidationError(
                field="operation",
                message=f"Template file not found: {template_name}",
                expected="existing template file",
                got=str(template_path),
                hint="Ensure Day 3 template files are deployed.",
                source="template_selector",
            )
        return template_path
