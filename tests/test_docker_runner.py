from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from llm_autofix_agents.docker_runner import (
    ContainerRunRequest,
    DockerRunner,
    ResourceLimits,
    resolve_dynamic_limits,
)


class DockerRunnerUnitTests(unittest.TestCase):
    def test_resource_limits_reject_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            ResourceLimits(cpus=0.0, memory="1g", pids_limit=256, timeout_seconds=120)

    def test_request_rejects_empty_command(self) -> None:
        with self.assertRaises(ValueError):
            ContainerRunRequest(repo_path=Path("."), command="   ")

    def test_build_docker_command_includes_hardening_flags(self) -> None:
        runner = DockerRunner()
        command = runner._build_docker_command(
            container_name="autofix-test",
            repo_path=Path("."),
            command="python --version",
            image="llm-autofix-runner:py313",
            limits=ResourceLimits(cpus=1.0, memory="1g", pids_limit=256, timeout_seconds=120),
        )
        self.assertIn("--init", command)
        self.assertIn("--security-opt", command)
        self.assertIn("no-new-privileges:true", command)
        self.assertIn("--cap-drop", command)
        self.assertIn("ALL", command)

    def test_resolve_dynamic_limits_small_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_path = Path(tmp_dir)
            (repo_path / "small.py").write_text("print('ok')\n", encoding="utf-8")
            limits = resolve_dynamic_limits(repo_path)
            self.assertEqual(limits.cpus, 1.0)
            self.assertEqual(limits.memory, "1g")
            self.assertEqual(limits.pids_limit, 256)
            self.assertEqual(limits.timeout_seconds, 120)


if __name__ == "__main__":
    unittest.main()
