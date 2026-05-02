from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from llm_autofix_agents.datasets.base import PreparedExecutionCase

logger = logging.getLogger(__name__)

_ERROR_CAPTURE_FALLBACK = "(error output not available)"


def generate_prompt(
    case: PreparedExecutionCase,
    template: str,
    error_output: str | None = None,
) -> str:
    resolved_error = error_output if error_output is not None else _ERROR_CAPTURE_FALLBACK
    variables = {
        **case.prompt_variables,
        "error_output": resolved_error,
    }
    return template.format(**variables)


def capture_error_output(
    repo_path: Path,
    test_command: str,
    timeout_seconds: int = 60,
) -> str | None:
    try:
        result = subprocess.run(
            test_command,
            shell=True,
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        parts: list[str] = []
        if result.stdout:
            parts.append(result.stdout.strip())
        if result.stderr:
            parts.append(result.stderr.strip())
        combined = "\n".join(parts)
        if not combined:
            return None
        return combined[-4000:] if len(combined) > 4000 else combined
    except subprocess.TimeoutExpired:
        logger.warning("Error capture timed out for test command: %s", test_command)
        return None
    except Exception:
        logger.warning("Error capture failed for test command: %s", test_command, exc_info=True)
        return None
