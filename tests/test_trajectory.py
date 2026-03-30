"""Tests for trajectory tracking and loop detection."""

from __future__ import annotations

import unittest

from agentbench.trajectory import Trajectory, TrajectoryStep, loop_penalty


class TestTrajectory(unittest.TestCase):
    def test_append_and_length(self) -> None:
        traj = Trajectory()
        traj.add("start", "begin")
        traj.add("tool_call", "search")
        traj.add("observation", "found 3 results")
        self.assertEqual(len(traj), 3)

    def test_to_list_round_trip(self) -> None:
        traj = Trajectory()
        traj.add("thought", "I should search")
        traj.add("tool_call", "search", tool="search")
        serialised = traj.to_list()
        restored = Trajectory.from_list(serialised)
        self.assertEqual(len(restored), 2)
        self.assertEqual(restored.steps[0].step_type, "thought")

    def test_tool_calls_extraction(self) -> None:
        traj = Trajectory()
        traj.add("tool_call", "search", tool="search")
        traj.add("observation", "result")
        traj.add("tool_call", "write", tool="write")
        self.assertEqual(traj.tool_calls(), ["search", "write"])

    def test_detect_loop_no_loop(self) -> None:
        traj = Trajectory()
        traj.add("thought", "step1")
        traj.add("tool_call", "search")
        traj.add("observation", "result1")
        traj.add("thought", "step2")
        traj.add("tool_call", "write")
        traj.add("observation", "result2")
        self.assertFalse(traj.detect_loop(window=3))

    def test_detect_loop_with_loop(self) -> None:
        traj = Trajectory()
        # First cycle
        traj.add("thought", "retry")
        traj.add("tool_call", "search")
        traj.add("observation", "fail")
        # Identical second cycle
        traj.add("thought", "retry")
        traj.add("tool_call", "search")
        traj.add("observation", "fail")
        self.assertTrue(traj.detect_loop(window=3))

    def test_loop_count(self) -> None:
        traj = Trajectory()
        for _ in range(4):
            traj.add("thought", "retry")
            traj.add("tool_call", "search")
            traj.add("observation", "fail")
        self.assertGreater(traj.loop_count(window=3), 0)


class TestLoopPenalty(unittest.TestCase):
    def test_no_penalty_for_clean_trajectory(self) -> None:
        traj = Trajectory()
        traj.add("thought", "a")
        traj.add("tool_call", "b")
        traj.add("observation", "c")
        self.assertEqual(loop_penalty(traj), 0.0)

    def test_penalty_applied(self) -> None:
        traj = Trajectory()
        for _ in range(4):
            traj.add("thought", "retry")
            traj.add("tool_call", "search")
            traj.add("observation", "fail")
        penalty = loop_penalty(traj)
        self.assertLess(penalty, 0.0)

    def test_penalty_capped(self) -> None:
        traj = Trajectory()
        for _ in range(20):
            traj.add("thought", "retry")
            traj.add("tool_call", "search")
            traj.add("observation", "fail")
        penalty = loop_penalty(traj, cap=0.60)
        self.assertGreaterEqual(penalty, -0.60)


if __name__ == "__main__":
    unittest.main()
