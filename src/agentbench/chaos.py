"""Chaos injection engine for resilience testing.

Wraps an MCPToolRegistry so that a configurable fraction of tool calls
return simulated failures (404, 429, 500, timeout).  The evaluator
can then score the agent on its ability to recover.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from agentbench.transport.protocol import MCPMessage, MCPToolRegistry


@dataclass(slots=True)
class ChaosConfig:
    """Configuration for the chaos engine."""

    failure_rate: float = 0.15
    failure_types: list[str] = field(default_factory=lambda: ["404", "429", "500", "timeout"])
    max_failures_per_tool: int = 2
    seed: int | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ChaosConfig":
        return cls(
            failure_rate=float(raw.get("failure_rate", 0.15)),
            failure_types=list(raw.get("failure_types", ["404", "429", "500", "timeout"])),
            max_failures_per_tool=int(raw.get("max_failures_per_tool", 2)),
            seed=raw.get("seed"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_rate": self.failure_rate,
            "failure_types": self.failure_types,
            "max_failures_per_tool": self.max_failures_per_tool,
            "seed": self.seed,
        }


_FAILURE_CODES: dict[str, tuple[int, str]] = {
    "404": (-32001, "404 Not Found: The requested resource does not exist."),
    "429": (-32002, "429 Too Many Requests: Rate limit exceeded. Retry after a short delay."),
    "500": (-32003, "500 Internal Server Error: An unexpected error occurred on the server."),
    "timeout": (-32004, "Request timed out. The server did not respond in time."),
}


class ChaosEngine:
    """Wraps an MCPToolRegistry to inject random tool failures."""

    def __init__(self, config: ChaosConfig) -> None:
        self.config = config
        self._rng = random.Random(config.seed)
        self._failure_counts: dict[str, int] = defaultdict(int)
        self._injection_log: list[dict[str, Any]] = []

    @property
    def injection_log(self) -> list[dict[str, Any]]:
        return list(self._injection_log)

    def wrap_registry(self, registry: MCPToolRegistry) -> "ChaosRegistry":
        """Return a new dispatch-compatible registry that randomly injects failures."""
        return ChaosRegistry(registry, self)

    def should_fail(self, tool_name: str) -> str | None:
        """Decide whether a call to *tool_name* should be injected with a failure.

        Returns the failure type string, or None if the call should pass through.
        """
        if self._failure_counts[tool_name] >= self.config.max_failures_per_tool:
            return None
        if self._rng.random() > self.config.failure_rate:
            return None
        failure_type = self._rng.choice(self.config.failure_types)
        self._failure_counts[tool_name] += 1
        self._injection_log.append({
            "tool": tool_name,
            "failure_type": failure_type,
            "total_failures": self._failure_counts[tool_name],
        })
        return failure_type


class ChaosRegistry:
    """Drop-in replacement for MCPToolRegistry.dispatch that injects failures."""

    def __init__(self, inner: MCPToolRegistry, engine: ChaosEngine) -> None:
        self._inner = inner
        self._engine = engine

    def dispatch(self, message: MCPMessage) -> MCPMessage:
        # Only inject failures on tool calls, not tool listing
        if message.method == "tools/call":
            tool_name = message.params.get("name", "")
            failure_type = self._engine.should_fail(tool_name)
            if failure_type is not None:
                code, msg_text = _FAILURE_CODES.get(failure_type, (-32000, "Unknown failure"))
                return MCPMessage.error_response(message.id, code, msg_text, {"injected": True, "failure_type": failure_type})
        return self._inner.dispatch(message)

    # Delegate everything else
    def manifest(self) -> list[dict[str, Any]]:
        return self._inner.manifest()

    @property
    def call_log(self) -> list[dict[str, Any]]:
        return self._inner.call_log

    def list_tools(self):
        return self._inner.list_tools()


def chaos_recovery_score(tool_log: list[dict[str, Any]]) -> float:
    """Score the agent on its ability to recover from injected failures.

    Returns 1.0 if the agent retried every failed tool call and eventually
    succeeded.  Returns 0.0 if the agent gave up after failures.
    """
    if not tool_log:
        return 1.0

    # Group by tool name
    calls_by_tool: dict[str, list[dict]] = defaultdict(list)
    for entry in tool_log:
        calls_by_tool[entry.get("tool", "")].append(entry)

    failed_tools = set()
    recovered_tools = set()

    for tool_name, calls in calls_by_tool.items():
        had_failure = False
        had_success_after = False
        for call in calls:
            status = call.get("status", "")
            if status in ("transient_error", "error") or call.get("error"):
                had_failure = True
            elif had_failure and status == "ok":
                had_success_after = True
        if had_failure:
            failed_tools.add(tool_name)
            if had_success_after:
                recovered_tools.add(tool_name)

    if not failed_tools:
        return 1.0
    return round(len(recovered_tools) / len(failed_tools), 4)
