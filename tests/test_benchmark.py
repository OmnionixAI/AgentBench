from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


class AgentBenchSmokeTests(unittest.TestCase):
    def test_list_command_outputs_core_tasks(self) -> None:
        completed = subprocess.run(
            [sys.executable, "-m", "agentbench", "list", "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=ENV,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("workflow.support_refund", completed.stdout)

    def test_reference_agent_smoke_suite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "runs"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "run",
                    "--output-dir",
                    str(output_dir),
                    "--task",
                    "workflow.support_refund",
                    "--seed",
                    "11",
                    "--agent-exec",
                    "python examples/agents/reference_agent.py",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=ENV,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('"passed": 1', completed.stdout)
            self.assertTrue((output_dir / "latest" / "summary.md").exists())

    def test_reference_agent_repo_patch_task(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "runs"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "run",
                    "--output-dir",
                    str(output_dir),
                    "--task",
                    "repo.timezone_window",
                    "--seed",
                    "11",
                    "--agent-python",
                    "examples/agents/reference_agent.py",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=ENV,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('"passed": 1', completed.stdout)
            self.assertTrue((output_dir / "latest" / "summary.md").exists())

    def test_prepare_and_init_adapter_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            adapter_path = Path(temp_dir) / "adapters" / "my_agent.py"
            prepared_dir = Path(temp_dir) / "prepared"
            init_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "init-adapter",
                    "--output",
                    str(adapter_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=ENV,
            )
            self.assertEqual(init_completed.returncode, 0, init_completed.stderr)
            self.assertTrue(adapter_path.exists())

            prepare_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "prepare",
                    "--task",
                    "data.margin_hotspots",
                    "--seed",
                    "11",
                    "--output-dir",
                    str(prepared_dir),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=ENV,
            )
            self.assertEqual(prepare_completed.returncode, 0, prepare_completed.stderr)
            self.assertIn('"task_id": "data.margin_hotspots"', prepare_completed.stdout)


if __name__ == "__main__":
    unittest.main()
