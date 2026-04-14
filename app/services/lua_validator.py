from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from tempfile import NamedTemporaryFile

from app.services.error_mapper import NormalizedValidationError


class LuaCodeValidator:
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

    def validate_syntax(self, lua_code: str) -> None:
        tmp_file: str | None = None
        container_name = f"octapi-luac-{uuid.uuid4().hex}"
        try:
            with NamedTemporaryFile("w", delete=False, suffix=".lua", encoding="utf-8") as handle:
                handle.write(lua_code)
                tmp_file = handle.name
            os.chmod(tmp_file, 0o644)

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
                "luac",
                "-p",
                "/work/script.lua",
            ]

            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            if proc.returncode != 0:
                raise NormalizedValidationError(
                    field="lua",
                    message=f"luac syntax check failed: {proc.stderr.strip() or proc.stdout.strip() or 'unknown luac error'}",
                    expected="valid Lua syntax",
                    got="syntax error",
                    hint="Fix Lua template rendering output before sandbox run.",
                    source="lua_syntax",
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
            raise NormalizedValidationError(
                field="lua",
                message=f"luac syntax check timed out after {self.timeout_seconds}s",
                expected="syntax check within timeout",
                got="timeout",
                hint="Check generated script size and container performance.",
                source="lua_syntax",
            ) from exc
        finally:
            if tmp_file is not None:
                Path(tmp_file).unlink(missing_ok=True)
