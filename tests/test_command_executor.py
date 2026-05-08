from pathlib import Path

from llm_autofix_agents.flow.execution.commands import CommandExecutor


def test_command_executor_runs_simple_command(tmp_path: Path) -> None:
    execution = CommandExecutor().execute_command(
        command="python -c 'print(123)'",
        cwd=tmp_path,
        timeout_seconds=10,
    )

    assert execution.exit_code == 0
    assert "123" in execution.stdout
    assert execution.error is None
