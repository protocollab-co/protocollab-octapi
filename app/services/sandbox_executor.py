from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
import subprocess
import uuid
from pathlib import Path

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
        self._runtime_log_path = Path("logs") / "runtime.log"

    def _append_runtime_log(
        self,
        *,
        status: str,
        exit_code: int,
        stdout: str,
        stderr: str,
        lua_code: str,
        context: dict[str, Any] | None,
    ) -> None:
        try:
            self._runtime_log_path.parent.mkdir(parents=True, exist_ok=True)
            if self._runtime_log_path.exists() and self._runtime_log_path.stat().st_size > 1_000_000:
                self._runtime_log_path.rename(self._runtime_log_path.with_suffix(".log.1"))

            ts = datetime.now(timezone.utc).isoformat()
            lua_preview = "\n".join(lua_code.splitlines()[:20])
            stdout_preview = "\n".join((stdout or "").splitlines()[:30])
            stderr_preview = "\n".join((stderr or "").splitlines()[:30])
            context_preview = repr(context)[:1200]
            record = (
                f"[{ts}] status={status} exit_code={exit_code}\n"
                f"context={context_preview}\n"
                f"lua_preview:\n{lua_preview}\n"
                f"stdout:\n{stdout_preview}\n"
                f"stderr:\n{stderr_preview}\n"
                "---\n"
            )
            with self._runtime_log_path.open("a", encoding="utf-8") as fp:
                fp.write(record)
        except Exception:
            # Logging failures must not affect sandbox execution path.
            return

    def build_script(self, lua_code: str, context: dict[str, Any] | None) -> str:
        lua_context = _to_lua_value(context or {})
        return (
            "local ctx = "
            + lua_context
            + "\n"
            + "local wf_ctx = (type(ctx.wf) == 'table' and ctx.wf) or {}\n"
            + "local wf = {\n"
            + "  vars = (type(wf_ctx.vars) == 'table' and wf_ctx.vars) or {},\n"
            + "  initVariables = (type(wf_ctx.initVariables) == 'table' and wf_ctx.initVariables) or {},\n"
            + "}\n"
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
        container_name = f"octapi-sandbox-{uuid.uuid4().hex}"
        try:
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
                "-i",
                self.docker_image,
                "lua",
                "-",
            ]
            proc = subprocess.run(
                command,
                input=script,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )

            self._append_runtime_log(
                status="success" if proc.returncode == 0 else "failed",
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                lua_code=lua_code,
                context=context,
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
            timeout_stderr = (exc.stderr or "") + f"\nExecution timed out after {self.timeout_seconds}s."
            self._append_runtime_log(
                status="timeout",
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=timeout_stderr,
                lua_code=lua_code,
                context=context,
            )
            return ExecutionResult(
                status="timeout",
                stdout=exc.stdout or "",
                stderr=timeout_stderr,
                exit_code=124,
            )
