from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
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

    def test_compare_command_detects_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            baseline_dir = Path(temp_dir) / "20260330-100000"
            current_dir = Path(temp_dir) / "20260331-100000"
            baseline_dir.mkdir(parents=True, exist_ok=True)
            current_dir.mkdir(parents=True, exist_ok=True)
            (baseline_dir / "summary.json").write_text(
                """
{
  "averages": {
    "overall": 0.847,
    "success": 0.873,
    "calibration": 0.912,
    "safety": 0.966,
    "recovery": 0.801,
    "efficiency": 0.793,
    "reliability": 0.923
  },
  "consistency": 0.923,
  "episodes": 9,
  "finops": {
    "avg_efficiency_score": 0.712,
    "cost_per_task_success": 0.52,
    "total_cost_usd": 4.68
  },
  "run_dir": "%s"
}
                """.strip()
                % str(baseline_dir).replace("\\", "\\\\"),
                encoding="utf-8",
            )
            (current_dir / "summary.json").write_text(
                """
{
  "averages": {
    "overall": 0.791,
    "success": 0.818,
    "calibration": 0.934,
    "safety": 0.971,
    "recovery": 0.756,
    "efficiency": 0.782,
    "reliability": 0.887
  },
  "consistency": 0.887,
  "episodes": 9,
  "finops": {
    "avg_efficiency_score": 0.701,
    "cost_per_task_success": 0.61,
    "total_cost_usd": 5.49
  },
  "run_dir": "%s"
}
                """.strip()
                % str(current_dir).replace("\\", "\\\\"),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "compare",
                    "--baseline",
                    str(baseline_dir),
                    "--current",
                    str(current_dir),
                    "--threshold",
                    "0.05",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=ENV,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertIn('"any_regression": true', completed.stdout)
            self.assertIn('"dimension": "overall"', completed.stdout)

    def test_compare_command_with_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "runs"
            older_dir = output_dir / "20260329-100000"
            current_dir = output_dir / "20260330-100000"
            latest_dir = output_dir / "latest"
            older_dir.mkdir(parents=True, exist_ok=True)
            current_dir.mkdir(parents=True, exist_ok=True)
            latest_dir.mkdir(parents=True, exist_ok=True)
            summary_payload = """
{
  "averages": {
    "overall": %s,
    "success": %s
  },
  "consistency": %s,
  "episodes": 2,
  "finops": {
    "avg_efficiency_score": null,
    "cost_per_task_success": null,
    "total_cost_usd": null
  },
  "run_dir": "%s"
}
            """.strip()
            (older_dir / "summary.json").write_text(summary_payload % ("0.80", "0.82", "0.90", str(older_dir).replace("\\", "\\\\")), encoding="utf-8")
            (current_dir / "summary.json").write_text(summary_payload % ("0.83", "0.84", "0.91", str(current_dir).replace("\\", "\\\\")), encoding="utf-8")
            (latest_dir / "summary.json").write_text(summary_payload % ("0.83", "0.84", "0.91", str(current_dir).replace("\\", "\\\\")), encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "compare",
                    "--current",
                    str(latest_dir),
                    "--output-dir",
                    str(output_dir),
                    "--window",
                    "1",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=ENV,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn('"baseline_timestamp": "2026-03-29T10:00:00Z"', completed.stdout)
            self.assertIn('"current_timestamp": "2026-03-30T10:00:00Z"', completed.stdout)

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

    def test_submit_and_build_leaderboard(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "runs"
            submissions_dir = Path(temp_dir) / "submissions"
            site_dir = Path(temp_dir) / "site"
            run_completed = subprocess.run(
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
            self.assertEqual(run_completed.returncode, 0, run_completed.stderr)

            summary_path = output_dir / "latest" / "summary.json"
            submit_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "submit",
                    "--summary",
                    str(summary_path),
                    "--submissions-dir",
                    str(submissions_dir),
                    "--agent-name",
                    "Reference Agent",
                    "--agent-version",
                    "0.2.9",
                    "--organization",
                    "Omnionix",
                    "--creator",
                    "Josh Verma",
                    "--framework",
                    "custom-cli",
                    "--model",
                    "gpt-test",
                    "--runtime",
                    "python",
                    "--integration",
                    "agent-python",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=ENV,
            )
            self.assertEqual(submit_completed.returncode, 0, submit_completed.stderr)
            self.assertIn('"submission_id"', submit_completed.stdout)

            build_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "build-leaderboard",
                    "--submissions-dir",
                    str(submissions_dir),
                    "--output-dir",
                    str(site_dir),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=ENV,
            )
            self.assertEqual(build_completed.returncode, 0, build_completed.stderr)
            leaderboard_payload = (site_dir / "leaderboard.json").read_text(encoding="utf-8")
            index_html = (site_dir / "index.html").read_text(encoding="utf-8")
            self.assertIn("Reference Agent", leaderboard_payload)
            self.assertIn("gpt-test", leaderboard_payload)
            self.assertIn("Public Leaderboard", index_html)

    def test_signed_submission_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "runs"
            submissions_dir = Path(temp_dir) / "submissions"
            site_dir = Path(temp_dir) / "site"
            signed_env = {**ENV, "AGENTBENCH_TEST_SIGNING_KEY": "super-secret-key"}
            run_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "run",
                    "--output-dir",
                    str(output_dir),
                    "--task",
                    "reliability.resume_handoff",
                    "--seed",
                    "17",
                    "--agent-python",
                    "examples/agents/reference_agent.py",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=signed_env,
            )
            self.assertEqual(run_completed.returncode, 0, run_completed.stderr)

            summary_path = output_dir / "latest" / "summary.json"
            submit_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "submit",
                    "--summary",
                    str(summary_path),
                    "--submissions-dir",
                    str(submissions_dir),
                    "--agent-name",
                    "Reference Agent Signed",
                    "--agent-version",
                    "0.2.9",
                    "--organization",
                    "Omnionix",
                    "--creator",
                    "Josh Verma",
                    "--framework",
                    "custom-cli",
                    "--model",
                    "gpt-test",
                    "--runtime",
                    "python",
                    "--integration",
                    "agent-python",
                    "--signing-key-env",
                    "AGENTBENCH_TEST_SIGNING_KEY",
                    "--key-id",
                    "test-maintainer",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=signed_env,
            )
            self.assertEqual(submit_completed.returncode, 0, submit_completed.stderr)
            submission_file = next(submissions_dir.glob("*.json"))
            submission_payload = submission_file.read_text(encoding="utf-8")
            self.assertIn('"signature"', submission_payload)
            self.assertIn('"key_id": "test-maintainer"', submission_payload)

            verify_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "verify-submission",
                    "--submission",
                    str(submission_file),
                    "--signing-key-env",
                    "AGENTBENCH_TEST_SIGNING_KEY",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=signed_env,
            )
            self.assertEqual(verify_completed.returncode, 0, verify_completed.stderr)
            self.assertIn('"valid": true', verify_completed.stdout)

            build_completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "build-leaderboard",
                    "--submissions-dir",
                    str(submissions_dir),
                    "--output-dir",
                    str(site_dir),
                    "--signing-key-env",
                    "AGENTBENCH_TEST_SIGNING_KEY",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=signed_env,
            )
            self.assertEqual(build_completed.returncode, 0, build_completed.stderr)
            leaderboard_payload = (site_dir / "leaderboard.json").read_text(encoding="utf-8")
            self.assertIn('"verification_status": "verified"', leaderboard_payload)
            self.assertIn('"verified": true', leaderboard_payload)

    def test_validate_submissions_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            submissions_dir = Path(temp_dir) / "submissions"
            submissions_dir.mkdir(parents=True, exist_ok=True)
            (submissions_dir / "bad.json").write_text('{"agent": {"name": "Broken"}}', encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "agentbench",
                    "validate-submissions",
                    "--submissions-dir",
                    str(submissions_dir),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
                env=ENV,
            )
            self.assertEqual(completed.returncode, 1)
            self.assertIn('"invalid": 1', completed.stdout)
            self.assertIn("Missing required agent fields", completed.stdout)


if __name__ == "__main__":
    unittest.main()
