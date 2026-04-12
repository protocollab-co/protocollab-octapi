from __future__ import annotations

from typing import Any
import subprocess
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.models import ExecutionResult
from app.services.error_mapper import NormalizedValidationError


def _to_lua_value(value: Any) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return f'"{escaped}"'
    if isinstance(value, list):
        items = ", ".join(_to_lua_value(item) for item in value)
        return "{" + items + "}"
    if isinstance(value, dict):
        chunks: list[str] = []
        for key, item in value.items():
            if isinstance(key, str):
                chunks.append(f"[{_to_lua_value(key)}] = {_to_lua_value(item)}")
            else:
                chunks.append(f"[{_to_lua_value(key)}] = {_to_lua_value(item)}")
        return "{" + ", ".join(chunks) + "}"
    return "nil"


class DockerSandboxExecutor:
    def __init__(
        self,
        docker_image: str,
        timeout_seconds: int,
        memory_mb: int,
        network_mode: str = "none",
    ) -> None:
        self.docker_image = docker_image
        self.timeout_seconds = timeout_seconds
        self.memory_mb = memory_mb
        self.network_mode = network_mode

    def build_script(self, lua_code: str, context: dict[str, Any] | None) -> str:
        lua_context = _to_lua_value(context or {})
        return (
            "local ctx = "
            + lua_context
            + "\n"
            + "local wf = ctx.wf or { vars = {}, initVariables = {} }\n"
            + lua_code
        )

    def is_available(self) -> bool:
        try:
            proc = subprocess.run(
                ["docker", "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            return proc.returncode == 0
        except Exception:
            return False

    def execute(self, lua_code: str, context: dict[str, Any] | None) -> ExecutionResult:
        script = self.build_script(lua_code=lua_code, context=context)
        tmp_file: str | None = None
        container_name = f"octapi-sandbox-{uuid.uuid4().hex}"
        try:
            with NamedTemporaryFile("w", delete=False, suffix=".lua", encoding="utf-8") as handle:
                handle.write(script)
                tmp_file = handle.name

            command = [
                "docker",
                "run",
                "--rm",
                "--name",
                container_name,
                "--network",
                self.network_mode,
                "--memory",
                f"{self.memory_mb}m",
                "--pids-limit",
                "64",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=16m",
                "--user",
                "65534:65534",
                "-v",
                f"{tmp_file}:/work/script.lua:ro",
                self.docker_image,
                "lua",
                "/work/script.lua",
            ]
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )

            return ExecutionResult(
                status="success" if proc.returncode == 0 else "failed",
                stdout=proc.stdout,
                stderr=proc.stderr,
                exit_code=proc.returncode,
            )
        except FileNotFoundError as exc:
            raise NormalizedValidationError(
                field="sandbox",
                message=f"Docker CLI not found: {exc}",
                expected="docker CLI available",
                got="docker unavailable",
                hint="Install Docker Desktop and ensure docker is in PATH.",
                source="sandbox",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, text=True, timeout=3, check=False)
            return ExecutionResult(
                status="timeout",
                stdout=exc.stdout or "",
                stderr=(exc.stderr or "") + f"\nExecution timed out after {self.timeout_seconds}s.",
                exit_code=124,
            )
        finally:
            if tmp_file is not None:
                Path(tmp_file).unlink(missing_ok=True)
