"""
Day 4 Runtime Contract Tests — Security Guards & Input Validation

Tests for:
- Lua string escaping (control chars: \\n, \\r, \\t)
- Execute endpoint input guards (session_id XOR yaml mutual exclusivity)
- Unsafe Lua expression rejection in parameters
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.services.lua_codegen import LuaCodeGenerator, to_lua


class TestLuaStringEscaping:
    """Verify control character escaping in Lua code generation."""

    def test_to_lua_escapes_control_chars(self):
        """Control chars (\\n, \\r, \\t) must be escaped in Lua strings."""
        from protocollab import expression

        # Test node with newline in string literal
        expr = expression.parse_expr('"hello\\nworld"')
        lua = to_lua(expr)
        assert '\\n' in lua, f"Expected escaped newline in {lua}"

        # Verify raw newline not in output
        assert '\n' not in lua, "Raw newline should not be in Lua code"

    def test_lua_escape_function_direct(self):
        """Test the _escape_lua_string filter directly."""
        from app.services.lua_codegen import LuaCodeGenerator
        
        codegen = LuaCodeGenerator(templates_dir=".")
        
        # Test control chars
        result = codegen._escape_lua_string("line1\nline2")
        assert "\\n" in result
        assert "\n" not in result
        
        # Test tabs and carriage returns
        result = codegen._escape_lua_string("col1\tcol2\rend")
        assert "\\t" in result
        assert "\\r" in result


class TestExecuteInputGuards:
    """Verify execute endpoint enforces input contract."""

    def test_session_id_and_yaml_mutual_exclusive(self):
        """Both session_id and yaml cannot be provided."""
        client = TestClient(app)
        response = client.post(
            "/execute",
            json={
                "session_id": "test123",
                "yaml": {"operation": "array_last", "parameters": {}},
            },
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_execute_payload"
        assert "either" in detail["message"].lower()

    def test_yaml_required_when_no_session_id(self):
        """YAML payload must be provided if session_id is not given."""
        client = TestClient(app)
        response = client.post("/execute", json={})
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "yaml" in detail["message"].lower()


class TestUnsafeExpressionRejection:
    """Verify parameter validation rejects unsafe Lua expressions."""

    def test_sanitize_params_rejects_unsafe_expressions(self, tmp_path):
        """Parameters containing unsafe Lua expressions must be rejected."""
        from app.services.error_mapper import NormalizedValidationError
        
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        octapi_dir = templates_dir / "octapi"
        octapi_dir.mkdir()

        # Create a simple template
        template = octapi_dir / "math_increment.lua.jinja2"
        template.write_text("result = 0 + {{ step }}")

        codegen = LuaCodeGenerator(templates_dir=str(templates_dir))

        # Unsafe: injection attempt via Lua comments/code
        with pytest.raises(NormalizedValidationError):
            codegen.generate_code(
                operation="math_increment",
                params={"step": "1; os.execute('rm -rf /')"},
                template_path=template,
            )

    def test_sanitize_params_validates_field_names(self, tmp_path):
        """Field name parameters must match safe patterns."""
        from app.services.error_mapper import NormalizedValidationError
        
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        octapi_dir = templates_dir / "octapi"
        octapi_dir.mkdir()

        template = octapi_dir / "array_filter.lua.jinja2"
        template.write_text("-- filter template")

        codegen = LuaCodeGenerator(templates_dir=str(templates_dir))

        # Unsafe: trying to inject Lua code in field name
        with pytest.raises(NormalizedValidationError):
            codegen.generate_code(
                operation="array_filter",
                params={"source": "x; print('hacked')"},
                template_path=template,
            )
