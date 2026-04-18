from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from llm_autofix_agents.flow.artifacts import persist_iteration_artifacts


class ArtifactsTests(unittest.TestCase):
    def test_persist_iteration_artifacts_writes_summary_and_file_trace(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            diff = (
                "diff --git a/src/a.py b/src/a.py\n"
                "index 111..222 100644\n"
                "--- a/src/a.py\n"
                "+++ b/src/a.py\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                "+new\n"
            )

            artifacts = persist_iteration_artifacts(
                repo_root=repo_root,
                run_id="run-123",
                iteration=1,
                diff=diff,
                changed_files=["src/a.py"],
                temp_branch="autofix/20260418T120000Z-run-123",
                ignore_rules=["build/", "*.pyc"],
            )

            file_changes_path = repo_root / artifacts["file_changes_file"]
            summary_path = repo_root / artifacts["patch_summary_file"]
            manifest_path = repo_root / artifacts["manifest_file"]

            self.assertTrue(file_changes_path.exists())
            self.assertTrue(summary_path.exists())
            self.assertTrue(manifest_path.exists())

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["temp_branch"], "autofix/20260418T120000Z-run-123")
            self.assertEqual(summary["totals"]["added_lines"], 1)
            self.assertEqual(summary["totals"]["deleted_lines"], 1)
            self.assertEqual(summary["files"][0]["path"], "src/a.py")

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn("files", manifest)
            self.assertIn("src/a.py", manifest["files"])
            self.assertEqual(manifest["files"]["src/a.py"]["first_seen_iteration"], 1)
            self.assertEqual(manifest["files"]["src/a.py"]["last_seen_iteration"], 1)

    def test_persist_iteration_artifacts_accumulates_manifest_file_trace(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            repo_root = Path(tmp_dir)
            run_id = "run-123"

            persist_iteration_artifacts(
                repo_root=repo_root,
                run_id=run_id,
                iteration=1,
                diff=(
                    "diff --git a/src/a.py b/src/a.py\n"
                    "index 111..222 100644\n"
                    "--- a/src/a.py\n"
                    "+++ b/src/a.py\n"
                    "@@ -1 +1 @@\n"
                    "-a\n"
                    "+aa\n"
                ),
                changed_files=["src/a.py"],
            )

            artifacts = persist_iteration_artifacts(
                repo_root=repo_root,
                run_id=run_id,
                iteration=2,
                diff=(
                    "diff --git a/src/a.py b/src/a.py\n"
                    "index 222..333 100644\n"
                    "--- a/src/a.py\n"
                    "+++ b/src/a.py\n"
                    "@@ -1 +1 @@\n"
                    "-aa\n"
                    "+aaa\n"
                ),
                changed_files=["src/a.py"],
            )

            manifest_path = repo_root / artifacts["manifest_file"]
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(manifest["iterations_count"], 2)
            self.assertEqual(manifest["files"]["src/a.py"]["first_seen_iteration"], 1)
            self.assertEqual(manifest["files"]["src/a.py"]["last_seen_iteration"], 2)
            self.assertEqual(manifest["files"]["src/a.py"]["total_added_lines"], 2)
            self.assertEqual(manifest["files"]["src/a.py"]["total_deleted_lines"], 2)


if __name__ == "__main__":
    unittest.main()
