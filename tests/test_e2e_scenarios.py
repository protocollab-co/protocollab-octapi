"""
Phase G: End-to-End Integration Tests (5 scenarios)

E2E scenarios for Day 1-4 flow:
1. Happy path: generate → execute (array_last)
2. Error + fix: generate error → ask clarification → execute
3. Context injection: execute with custom context variables
4. Condition error: array_filter with invalid condition → feedback
5. Math operation: math_increment with numeric parameters

NOTE: Execute tests require Docker. They will be skipped if Docker unavailable.
"""

import json
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def is_docker_available():
    """Check if Docker is available on this system."""
    from app.services.sandbox_executor import DockerSandboxExecutor
    from app.config import get_settings
    
    settings = get_settings()
    executor = DockerSandboxExecutor(
        docker_image=settings.docker_image,
        timeout_seconds=settings.sandbox_timeout_seconds,
        memory_mb=settings.sandbox_memory_mb,
        network_mode=settings.sandbox_network_mode,
    )
    return executor.is_available()


pytestmark = pytest.mark.skipif(
    not is_docker_available(),
    reason="Docker not available - execute tests skipped"
)


class TestE2EHappyPath:
    """Scenario 1: Successful YAML generation and Lua execution."""

    def test_array_last_inline_success(self, client):
        """Generate array_last YAML and execute with inline context."""
        # Step 1: Generate YAML
        response = client.post(
            "/generate",
            json={"prompt": "Get last email from the list"},
        )
        assert response.status_code == 200
        gen_data = response.json()
        
        assert gen_data["is_complete"] == True, f"Generate failed: {gen_data.get('feedback')}"
        assert gen_data["yaml"]["operation"] in ["array_last"]
        
        # Step 2: Execute generated YAML with context
        execute_response = client.post(
            "/execute",
            json={
                "session_id": gen_data["session_id"],
                "context": {
                    "wf": {
                        "vars": {
                            "emails": ["alice@example.com", "bob@example.com", "charlie@example.com"]
                        }
                    }
                }
            }
        )
        assert execute_response.status_code == 200
        exec_data = execute_response.json()
        
        assert exec_data["operation"] == "array_last"
        assert exec_data["execution_result"]["status"] == "success"
        assert "charlie@example.com" in exec_data["execution_result"]["stdout"] or "3" in exec_data["execution_result"]["stdout"]


class TestE2EErrorAndFix:
    """Scenario 2: Error in generation → ask for clarification → success."""

    def test_invalid_operation_fix_via_ask(self, client):
        """Invalid operation → ask clarification → valid YAML."""
        # Step 1: Generate with ambiguous prompt (may cause error)
        response = client.post(
            "/generate",
            json={"prompt": "Do something with the list"},  # Vague
        )
        gen_data = response.json()
        
        # If generation failed (is_complete: false)
        if not gen_data["is_complete"]:
            assert len(gen_data["feedback"]) > 0
            
            # Step 2: Ask for clarification
            ask_response = client.post(
                "/ask",
                json={
                    "session_id": gen_data["session_id"],
                    "question": "Extract the last item from the list"
                }
            )
            assert ask_response.status_code == 200
            ask_data = ask_response.json()
            
            # Should eventually succeed or provide new feedback
            if ask_data["is_complete"]:
                assert ask_data["yaml"]["operation"] in ["array_last", "ensure_array_field"]
            else:
                # If still failed, verify feedback loop works
                assert len(ask_data["feedback"]) > 0
        else:
            # If generation succeeded, we can proceed to execute
            assert gen_data["yaml"]["operation"] in ["array_last", "ensure_array_field", "object_clean"]


class TestE2EContextInjection:
    """Scenario 3: Execute with custom context variables."""

    def test_execute_with_custom_context(self, client):
        """Execute array_last with injected context."""
        response = client.post(
            "/execute",
            json={
                "yaml": {
                    "operation": "array_last",
                    "parameters": {"source": "wf.vars.items"}
                },
                "context": {
                    "wf": {
                        "vars": {
                            "items": [{"id": 1, "name": "Item A"}, {"id": 2, "name": "Item B"}]
                        }
                    }
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["execution_result"]["status"] == "success"
        # Result should be the last item (Item B)
        assert "Item B" in data["execution_result"]["stdout"] or "2" in data["execution_result"]["stdout"]


class TestE2EConditionError:
    """Scenario 4: array_filter with invalid condition → feedback."""

    def test_array_filter_condition_error(self, client):
        """array_filter generates feedback if condition is invalid."""
        response = client.post(
            "/generate",
            json={
                "prompt": "Filter numbers greater than 5"
            }
        )
        gen_data = response.json()
        
        # array_filter requires valid condition, may get error
        if not gen_data["is_complete"] and len(gen_data.get("feedback", [])) > 0:
            feedback = gen_data["feedback"][0]
            # Feedback structure should include field, message, etc.
            assert "field" in feedback
            assert "message" in feedback
            assert "source" in feedback


class TestE2EMathIncrement:
    """Scenario 5: math_increment operation with numeric parameters."""

    def test_math_increment_execution(self, client):
        """Execute math_increment with numeric parameter."""
        response = client.post(
            "/execute",
            json={
                "yaml": {
                    "operation": "math_increment",
                    "parameters": {
                        "target_field": "counter",
                        "step": 5
                    }
                },
                "context": {
                    "wf": {
                        "vars": {
                            "counter": 10
                        }
                    }
                }
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "math_increment"
        assert data["execution_result"]["status"] == "success"
        # Result should be 10 + 5 = 15
        assert "15" in data["execution_result"]["stdout"]


class TestE2EHealthCheck:
    """Verify health endpoint returns correct status."""

    def test_health_returns_docker_available(self, client):
        """Health check should report Docker availability."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] in ["ok", "degraded"]
        assert "ollama" in data
        assert "docker" in data
        assert data["docker"] in ["available", "unavailable"]


class TestE2EMutualExclusivity:
    """Verify /execute enforces session_id XOR yaml."""

    def test_execute_requires_either_session_or_yaml(self, client):
        """Execute endpoint must reject both/neither session_id and yaml."""
        
        # Case 1: Both provided (invalid)
        response = client.post(
            "/execute",
            json={
                "session_id": "abc123",
                "yaml": {"operation": "array_last", "parameters": {}}
            }
        )
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_execute_payload"
        
        # Case 2: Neither provided (invalid)
        response = client.post("/execute", json={})
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert detail["code"] == "invalid_execute_payload"
        
        # Case 3: Only YAML (valid)
        response = client.post(
            "/execute",
            json={
                "yaml": {
                    "operation": "array_last",
                    "parameters": {"source": "data"}
                },
                "context": {"wf": {"vars": {"data": [1, 2, 3]}}}
            }
        )
        assert response.status_code == 200


# ===== SMOKE TESTS =====

class TestSmokeChecklist:
    """Final smoke tests to ensure MVP readiness."""

    def test_all_endpoints_exist(self, client):
        """Verify all required endpoints exist."""
        endpoints = [
            ("GET", "/"),
            ("GET", "/health"),
            ("POST", "/generate"),
            ("POST", "/ask"),
            ("POST", "/execute"),
        ]
        
        for method, path in endpoints:
            if method == "GET":
                resp = client.get(path)
            else:
                resp = client.post(path, json={})
            
            # Endpoint exists if not 404 (may be 400 for missing data, that's OK)
            assert resp.status_code != 404, f"Endpoint {method} {path} not found"

    def test_response_schemas_valid(self, client):
        """Verify response JSON schmas are valid."""
        # Health check
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        health = health_resp.json()
        assert "status" in health and "ollama" in health
        
    def test_error_format_consistent(self, client):
        """Verify error responses use consistent format."""
        # Trigger error
        response = client.post("/execute", json={})
        assert response.status_code == 400
        
        detail = response.json()["detail"]
        assert isinstance(detail, dict)
        assert "code" in detail or "message" in detail
