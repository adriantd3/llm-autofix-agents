from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

from llm_autofix_agents.contracts import TestResults
from llm_autofix_agents.flow.models import TestExecution


def resolve_test_timeout_seconds(metadata: dict[str, object]) -> int:
    value = metadata.get("test_timeout_seconds")
    if value is None:
        return 120
    if not isinstance(value, int):
        raise ValueError("metadata.test_timeout_seconds must be an integer")
    if value < 1 or value > 1800:
        raise ValueError("metadata.test_timeout_seconds must be between 1 and 1800")
    return value


def run_test_command(test_command: str | None, *, cwd: Path, timeout_seconds: int) -> TestExecution:
    if test_command is None:
        return TestExecution(exit_code=0, timed_out=False, output="", signature="no-tests")

    try:
        completed = subprocess.run(
            test_command,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = f"{completed.stdout}\n{completed.stderr}".strip()
        signature = build_test_signature(exit_code=completed.returncode, timed_out=False, output=output)
        return TestExecution(
            exit_code=completed.returncode,
            timed_out=False,
            output=output,
            signature=signature,
        )
    except subprocess.TimeoutExpired as exc:
        output = f"timeout: {exc}"
        signature = build_test_signature(exit_code=124, timed_out=True, output=output)
        return TestExecution(exit_code=124, timed_out=True, output=output, signature=signature)


def build_test_signature(*, exit_code: int, timed_out: bool, output: str) -> str:
    normalized_output = " ".join(output.split()).strip().lower()
    payload = f"exit={exit_code}|timed_out={timed_out}|{normalized_output}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def to_test_results(test_execution: TestExecution) -> TestResults:
    output = test_execution.output
    total = extract_int(output, r"Ran\s+(\d+)\s+tests?")

    passed = sum_counts(output, [r"(\d+)\s+passed"])
    failed = sum_counts(
        output,
        [
            r"(\d+)\s+failed",
            r"failures?=(\d+)",
            r"errors?=(\d+)",
        ],
    )

    if test_execution.exit_code == 0 and failed == 0:
        if total == 0:
            total = passed
        return TestResults(total=total, passed=passed, failed=0)

    if failed == 0:
        failed = 1

    if total < passed + failed:
        total = passed + failed

    return TestResults(total=total, passed=passed, failed=failed)


def extract_int(text: str, pattern: str) -> int:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match is None:
        return 0
    return int(match.group(1))


def sum_counts(text: str, patterns: list[str]) -> int:
    total = 0
    for pattern in patterns:
        for value in re.findall(pattern, text, flags=re.IGNORECASE):
            total += int(value)
    return total
