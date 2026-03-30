"""Tests for the FinOps cost tracker."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agentbench.finops import (
    compute_cost,
    cost_per_task_success,
    efficiency_score,
    parse_token_report,
)


class TestParseTokenReport(unittest.TestCase):
    def test_from_workspace_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            report = {"model": "gpt-4o", "input_tokens": 10000, "output_tokens": 2000}
            (workspace / "token_report.json").write_text(json.dumps(report), encoding="utf-8")
            result = parse_token_report(workspace=workspace)
            self.assertIsNotNone(result)
            self.assertEqual(result["model"], "gpt-4o")
            self.assertEqual(result["input_tokens"], 10000)

    def test_from_stdout_markers(self) -> None:
        stdout = (
            "some output\n"
            "[AGENTBENCH_TOKENS]{\"model\": \"claude-sonnet-4\", \"input_tokens\": 5000, \"output_tokens\": 1000}[/AGENTBENCH_TOKENS]\n"
            "more output\n"
        )
        result = parse_token_report(stdout=stdout)
        self.assertIsNotNone(result)
        self.assertEqual(result["model"], "claude-sonnet-4")

    def test_returns_none_when_no_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = parse_token_report(workspace=Path(tmp), stdout="no markers here")
            self.assertIsNone(result)


class TestComputeCost(unittest.TestCase):
    def test_gpt4o_cost(self) -> None:
        report = {"model": "gpt-4o", "input_tokens": 10000, "output_tokens": 2000}
        cost = compute_cost(report)
        # 10K * 0.0025/1K + 2K * 0.010/1K = 0.025 + 0.02 = 0.045
        self.assertAlmostEqual(cost, 0.045, places=4)

    def test_unknown_model_falls_back(self) -> None:
        report = {"model": "my-custom-model", "input_tokens": 1000, "output_tokens": 500}
        cost = compute_cost(report)
        self.assertGreater(cost, 0)


class TestCostPerTaskSuccess(unittest.TestCase):
    def test_normal(self) -> None:
        self.assertAlmostEqual(cost_per_task_success(0.10, 2), 0.05, places=4)

    def test_zero_passed(self) -> None:
        result = cost_per_task_success(0.05, 0)
        self.assertEqual(result, float("inf"))


class TestEfficiencyScore(unittest.TestCase):
    def test_high_accuracy_low_cost(self) -> None:
        score = efficiency_score(accuracy=1.0, cost_usd=0.001, latency_seconds=5.0)
        self.assertGreater(score, 0.5)

    def test_zero_accuracy(self) -> None:
        score = efficiency_score(accuracy=0.0, cost_usd=0.1, latency_seconds=10.0)
        self.assertEqual(score, 0.0)

    def test_bounded_to_one(self) -> None:
        score = efficiency_score(accuracy=1.0, cost_usd=0.0001, latency_seconds=0.1)
        self.assertLessEqual(score, 1.0)


if __name__ == "__main__":
    unittest.main()
