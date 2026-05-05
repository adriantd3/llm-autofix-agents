from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from llm_autofix_agents.batch.runner import BatchRunner


class MainCliTests(unittest.TestCase):
    def test_batch_command_exists(self) -> None:
        """Verify that 'autofix batch' is available."""
        from llm_autofix_agents.main import _build_parser

        parser = _build_parser()
        # Should not raise when parsing batch command
        args = parser.parse_args(["batch", "test.yaml"])
        self.assertEqual(args.command_name, "batch")
        self.assertEqual(args.config, Path("test.yaml"))

    def test_batch_requires_config_argument(self) -> None:
        """Verify that batch command requires a config file."""
        from llm_autofix_agents.main import _build_parser

        parser = _build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["batch"])

    def test_batch_accepts_optional_arguments(self) -> None:
        """Verify that batch command accepts optional arguments."""
        from llm_autofix_agents.main import _build_parser

        parser = _build_parser()
        args = parser.parse_args(
            [
                "batch",
                "config.yaml",
                "--compose-file",
                "custom-compose.yml",
                "--project-dir",
                "/some/path",
                "--dry-run",
            ]
        )
        self.assertEqual(args.command_name, "batch")
        self.assertEqual(args.config, Path("config.yaml"))
        self.assertEqual(args.compose_file, Path("custom-compose.yml"))
        self.assertEqual(args.project_dir, Path("/some/path"))
        self.assertTrue(args.dry_run)

    @patch("llm_autofix_agents.main.BatchRunner")
    def test_run_batch_invokes_runner(self, mocked_batch_runner_class: MagicMock) -> None:
        """Verify that _run_batch invokes BatchRunner with correct arguments."""
        from llm_autofix_agents.main import _run_batch

        mocked_runner = MagicMock()
        mocked_runner.run_batch.return_value = MagicMock(model_dump_json=lambda: "{}")
        mocked_batch_runner_class.return_value = mocked_runner

        args = MagicMock()
        args.config = Path("/path/to/config.yaml")
        args.project_dir = Path("/project")
        args.compose_file = Path("docker-compose.yml")
        args.dry_run = False

        with patch("builtins.print"):
            exit_code = _run_batch(args)

        self.assertEqual(exit_code, 0)
        mocked_batch_runner_class.assert_called_once()


if __name__ == "__main__":
    unittest.main()
