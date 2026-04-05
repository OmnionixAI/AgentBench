from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import os
from argparse import Namespace
from pathlib import Path

from agentbench.cli import build_agent_command


ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src")}


class AgentBenchSmokeTests(unittest.TestCase):
    @staticmethod
    def _docker_daemon_available() -> bool:
        completed = subprocess.run(
            ["docker", "info"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            env=ENV,
        )
        return completed.returncode == 0

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
        self.assertIn("reliability.memory_refresh", completed.stdout)
        self.assertIn("mcp.file_organise", completed.stdout)

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

    def test_reference_agent_reliability_task(self) -> None:
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
                    "reliability.memory_refresh",
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

    def test_reference_agent_mcp_task(self) -> None:
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
                    "mcp.file_organise",
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

    def test_build_docker_agent_command(self) -> None:
        command = build_agent_command(
            Namespace(
                agent_command=None,
                agent_exec=None,
                agent_python=None,
                agent_docker_image="my-agent:latest",
                agent_docker_command="run-agent",
                agent_docker_args="-e OPENAI_API_KEY=test",
            )
        )
        self.assertIn("docker run --rm", command)
        self.assertIn("my-agent:latest", command)
        self.assertIn("--task \"{docker_task_file}\"", command)
        self.assertIn("-e OPENAI_API_KEY=test", command)

    def test_reference_agent_docker_path(self) -> None:
        if not self._docker_daemon_available():
            self.skipTest("Docker daemon is not available on this machine.")
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
                    "--agent-docker-image",
                    "python:3.13-slim",
                    "--agent-docker-command",
                    "python /agentbench_host_repo/examples/agents/reference_agent.py",
                    "--agent-docker-args",
                    "-e PYTHONPATH=/agentbench_host_repo/src",
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


if __name__ == "__main__":
    unittest.main()
