from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandExecution:
    exit_code: int | None
    stdout: str
    stderr: str
    error: str | None = None


@dataclass(frozen=True)
class CommandExecutor:
    max_output_chars: int = 12_000

    def run(
        self,
        *,
        command: str,
        cwd: Path,
        timeout_seconds: int,
        env_overrides: dict[str, str] | None = None,
        use_bash_lc: bool = False,
    ) -> CommandExecution:
        env = {**os.environ, **(env_overrides or {})}
        process_command: str | list[str] = command
        shell = True
        if use_bash_lc:
            process_command = ["bash", "-lc", command]
            shell = False
        try:
            completed = subprocess.run(
                process_command,
                cwd=str(cwd),
                shell=shell,
                capture_output=True,
                text=True,
                timeout=max(1, timeout_seconds),
                check=False,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            stdout, _ = self._truncate(exc.stdout or "")
            stderr, _ = self._truncate(exc.stderr or "")
            return CommandExecution(
                exit_code=124,
                stdout=stdout,
                stderr=stderr,
                error="timeout",
            )

        stdout, _ = self._truncate(completed.stdout)
        stderr, _ = self._truncate(completed.stderr)
        return CommandExecution(
            exit_code=completed.returncode,
            stdout=stdout,
            stderr=stderr,
        )

    def _truncate(self, text: str) -> tuple[str, bool]:
        if len(text) <= self.max_output_chars:
            return text, False
        return text[: self.max_output_chars], True
