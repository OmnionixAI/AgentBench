"""Tests for the YAML/JSON scenario loader."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agentbench.scenario_loader import load_auto, load_scenario, load_scenario_dir


_YAML_CONTENT = """\
suite:
  name: "Test Suite"
  version: "1.0.0"
  description: "A test suite."

weights:
  success: 0.60
  safety: 0.20
  recovery: 0.10
  efficiency: 0.10

tasks:
  - id: test.task_one
    title: "Task One"
    family: repo_patch
    scenario: timezone_window
    difficulty: easy
    description: "A simple task."
    tags: [test]
    default_seeds: [1, 2]
    budget:
      max_runtime_seconds: 60
"""


class TestLoadScenarioYAML(unittest.TestCase):
    def test_load_single_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "suite.yaml"
            path.write_text(_YAML_CONTENT, encoding="utf-8")
            suite = load_scenario(path)
            self.assertEqual(suite.name, "Test Suite")
            self.assertEqual(len(suite.tasks), 1)
            self.assertEqual(suite.tasks[0].id, "test.task_one")

    def test_load_json_compat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "suite.json"
            payload = {
                "name": "JSON Suite",
                "version": "0.1.0",
                "description": "Test.",
                "weights": {"success": 0.55, "safety": 0.15, "recovery": 0.15, "efficiency": 0.10, "calibration": 0.05},
                "tasks": [
                    {"id": "json.task", "title": "T", "family": "repo_patch", "scenario": "timezone_window",
                     "difficulty": "easy", "description": "D", "tags": [], "default_seeds": [1], "budget": {}}
                ],
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            suite = load_scenario(path)
            self.assertEqual(suite.name, "JSON Suite")
            self.assertEqual(len(suite.tasks), 1)


class TestLoadScenarioDir(unittest.TestCase):
    def test_merge_multiple_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p1 = Path(tmp) / "a.yaml"
            p1.write_text(_YAML_CONTENT, encoding="utf-8")

            p2 = Path(tmp) / "b.json"
            payload = {
                "name": "B Suite",
                "version": "1.0.0",
                "description": "B.",
                "weights": {"success": 0.55},
                "tasks": [
                    {"id": "b.task", "title": "BT", "family": "repo_patch", "scenario": "rate_limit_boundary",
                     "difficulty": "medium", "description": "BD", "tags": [], "default_seeds": [3], "budget": {}}
                ],
            }
            p2.write_text(json.dumps(payload), encoding="utf-8")

            suite = load_scenario_dir(Path(tmp))
            self.assertEqual(len(suite.tasks), 2)
            ids = {t.id for t in suite.tasks}
            self.assertIn("test.task_one", ids)
            self.assertIn("b.task", ids)


class TestLoadAuto(unittest.TestCase):
    def test_auto_detects_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "suite.yaml"
            path.write_text(_YAML_CONTENT, encoding="utf-8")
            suite = load_auto(path)
            self.assertEqual(suite.name, "Test Suite")

    def test_auto_detects_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "suite.yaml"
            path.write_text(_YAML_CONTENT, encoding="utf-8")
            suite = load_auto(Path(tmp))
            self.assertEqual(len(suite.tasks), 1)


if __name__ == "__main__":
    unittest.main()
