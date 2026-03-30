"""Tests for the tool-selection entropy metric."""

from __future__ import annotations

import unittest

from agentbench.metrics.entropy import tool_selection_entropy


class TestToolSelectionEntropy(unittest.TestCase):
    def test_perfect_selection(self) -> None:
        """Agent only called the correct tool."""
        calls = ["search", "search", "search"]
        correct = {"search"}
        score = tool_selection_entropy(calls, correct, total_available=50)
        self.assertGreater(score, 0.9)

    def test_random_selection(self) -> None:
        """Agent called many different tools randomly."""
        calls = [f"tool_{i}" for i in range(50)]
        correct = {"tool_0"}
        score = tool_selection_entropy(calls, correct, total_available=50)
        self.assertLess(score, 0.3)

    def test_mixed_selection(self) -> None:
        """Agent called some correct and some incorrect tools."""
        calls = ["search", "search", "weather", "search", "translate"]
        correct = {"search"}
        score = tool_selection_entropy(calls, correct, total_available=50)
        self.assertGreater(score, 0.3)
        self.assertLess(score, 0.95)

    def test_empty_calls(self) -> None:
        score = tool_selection_entropy([], {"search"}, total_available=50)
        self.assertEqual(score, 0.0)

    def test_single_available(self) -> None:
        score = tool_selection_entropy(["only"], {"only"}, total_available=1)
        self.assertEqual(score, 0.0)

    def test_all_wrong(self) -> None:
        calls = ["wrong1", "wrong2", "wrong3"]
        correct = {"right"}
        score = tool_selection_entropy(calls, correct, total_available=50)
        self.assertEqual(score, 0.0)


if __name__ == "__main__":
    unittest.main()
