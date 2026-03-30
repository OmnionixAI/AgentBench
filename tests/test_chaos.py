"""Tests for the chaos injection engine."""

from __future__ import annotations

import unittest

from agentbench.chaos import ChaosConfig, ChaosEngine, chaos_recovery_score
from agentbench.transport.protocol import MCPMessage, MCPToolRegistry


class TestChaosEngine(unittest.TestCase):
    def test_no_failures_at_zero_rate(self) -> None:
        config = ChaosConfig(failure_rate=0.0, seed=42)
        engine = ChaosEngine(config)
        for _ in range(100):
            self.assertIsNone(engine.should_fail("test_tool"))

    def test_guaranteed_failures_at_full_rate(self) -> None:
        config = ChaosConfig(failure_rate=1.0, max_failures_per_tool=3, seed=42)
        engine = ChaosEngine(config)
        failures = 0
        for _ in range(10):
            if engine.should_fail("test_tool") is not None:
                failures += 1
        self.assertEqual(failures, 3)  # capped at max_failures_per_tool

    def test_injection_log_records_failures(self) -> None:
        config = ChaosConfig(failure_rate=1.0, max_failures_per_tool=2, seed=42)
        engine = ChaosEngine(config)
        engine.should_fail("a")
        engine.should_fail("b")
        self.assertEqual(len(engine.injection_log), 2)

    def test_wrap_registry_injects_failures(self) -> None:
        registry = MCPToolRegistry()
        registry.register_simple("add", "Add", lambda args: args["a"] + args["b"])
        config = ChaosConfig(failure_rate=1.0, max_failures_per_tool=1, seed=42)
        engine = ChaosEngine(config)
        wrapped = engine.wrap_registry(registry)

        msg = MCPMessage.request("tools/call", {"name": "add", "arguments": {"a": 1, "b": 2}})
        resp = wrapped.dispatch(msg)
        self.assertIsNotNone(resp.error)  # First call should fail

        resp2 = wrapped.dispatch(msg)
        self.assertIsNotNone(resp2.result)  # Second call should pass through

    def test_tool_listing_not_affected(self) -> None:
        registry = MCPToolRegistry()
        registry.register_simple("add", "Add", lambda args: 0)
        config = ChaosConfig(failure_rate=1.0, seed=42)
        engine = ChaosEngine(config)
        wrapped = engine.wrap_registry(registry)

        msg = MCPMessage.request("tools/list")
        resp = wrapped.dispatch(msg)
        self.assertIsNotNone(resp.result)
        self.assertEqual(len(resp.result["tools"]), 1)


class TestChaosRecoveryScore(unittest.TestCase):
    def test_perfect_recovery(self) -> None:
        log = [
            {"tool": "search", "status": "transient_error"},
            {"tool": "search", "status": "ok"},
        ]
        self.assertEqual(chaos_recovery_score(log), 1.0)

    def test_no_recovery(self) -> None:
        log = [
            {"tool": "search", "status": "transient_error"},
            {"tool": "other", "status": "ok"},
        ]
        self.assertEqual(chaos_recovery_score(log), 0.0)

    def test_no_failures(self) -> None:
        log = [{"tool": "search", "status": "ok"}]
        self.assertEqual(chaos_recovery_score(log), 1.0)

    def test_empty_log(self) -> None:
        self.assertEqual(chaos_recovery_score([]), 1.0)


if __name__ == "__main__":
    unittest.main()
