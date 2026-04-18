from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llm_autofix_agents.runtime.docker_runner import (
    ContainerRunRequest,
    DockerRunner,
    DockerRunnerError,
    ResourceLimits,
    resolve_dynamic_limits,
)


class DockerRunnerUnitTests(unittest.TestCase):
    def test_resource_limits_reject_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            ResourceLimits(cpus=0.0, timeout_seconds=120)

    def test_request_rejects_empty_command(self) -> None:
        with self.assertRaises(ValueError):
            ContainerRunRequest(repo_path=Path("."), command="   ")

    def test_request_rejects_non_directory_repo_path(self) -> None:
        with self.assertRaises(ValueError):
            ContainerRunRequest(repo_path=Path("missing-dir"), command="echo ok")

    def test_runner_rejects_empty_constructor_values(self) -> None:
        with self.assertRaises(ValueError):
            DockerRunner(docker_executable=" ")
        with self.assertRaises(ValueError):
            DockerRunner(network_mode=" ")

    def test_build_docker_command_is_minimal_for_mvp(self) -> None:
        runner = DockerRunner()
        command = runner._build_docker_command(
            container_name="autofix-test",
            repo_path=Path("."),
            command="python --version",
            image="llm-autofix-runner:py313",
            limits=ResourceLimits(timeout_seconds=120),
        )
        self.assertIn("--rm", command)
        self.assertIn("--workdir", command)
        self.assertIn("--mount", command)
        self.assertNotIn("--cpus", command)
        self.assertNotIn("--memory", command)
        self.assertNotIn("--pids-limit", command)

    def test_resolve_dynamic_limits_returns_simple_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir)
            (repo_path / "small.py").write_text("print('ok')\n", encoding="utf-8")
            limits = resolve_dynamic_limits(repo_path)
            self.assertIsNone(limits.cpus)
            self.assertIsNone(limits.memory)
            self.assertIsNone(limits.pids_limit)
            self.assertEqual(limits.timeout_seconds, 300)

    def test_assert_docker_available_uses_stdout_when_stderr_empty(self) -> None:
        runner = DockerRunner()
        with patch("llm_autofix_agents.runtime.docker_runner.subprocess.run") as mocked_run:
            mocked_run.return_value.returncode = 1
            mocked_run.return_value.stderr = ""
            mocked_run.return_value.stdout = "docker daemon unreachable"

            with self.assertRaises(DockerRunnerError) as exc:
                runner.assert_docker_available()

        self.assertIn("docker daemon unreachable", str(exc.exception))


if __name__ == "__main__":
    unittest.main()
