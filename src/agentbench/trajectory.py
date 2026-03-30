"""Trajectory tracking for agent evaluation.

Records every step of an agent's execution (thoughts, tool calls, observations,
errors) and provides loop detection / penalty scoring.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TrajectoryStep:
    """A single step in the agent's execution trajectory."""

    step_type: str  # "thought" | "tool_call" | "observation" | "error" | "start" | "finish"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_type": self.step_type,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TrajectoryStep":
        return cls(
            step_type=raw["step_type"],
            content=raw["content"],
            timestamp=raw.get("timestamp", 0.0),
            metadata=raw.get("metadata", {}),
        )


class Trajectory:
    """Ordered sequence of trajectory steps with analysis helpers."""

    def __init__(self) -> None:
        self._steps: list[TrajectoryStep] = []

    def append(self, step: TrajectoryStep) -> None:
        self._steps.append(step)

    def add(self, step_type: str, content: str, **metadata: Any) -> None:
        self._steps.append(TrajectoryStep(step_type=step_type, content=content, metadata=metadata))

    def __len__(self) -> int:
        return len(self._steps)

    @property
    def steps(self) -> list[TrajectoryStep]:
        return list(self._steps)

    def to_list(self) -> list[dict[str, Any]]:
        return [step.to_dict() for step in self._steps]

    @classmethod
    def from_list(cls, raw: list[dict[str, Any]]) -> "Trajectory":
        traj = cls()
        for item in raw:
            traj._steps.append(TrajectoryStep.from_dict(item))
        return traj

    def _signature(self, step: TrajectoryStep) -> str:
        """Fingerprint a step for loop detection."""
        return f"{step.step_type}:{step.content}"

    def detect_loop(self, window: int = 3) -> bool:
        """Check if the last *window* steps repeat an earlier contiguous block."""
        if len(self._steps) < window * 2:
            return False
        tail = [self._signature(s) for s in self._steps[-window:]]
        # Scan backwards for an identical window
        for start in range(len(self._steps) - window * 2, -1, -1):
            candidate = [self._signature(s) for s in self._steps[start : start + window]]
            if candidate == tail:
                return True
        return False

    def loop_count(self, window: int = 3) -> int:
        """Count distinct repeated cycles of length *window*."""
        if len(self._steps) < window * 2:
            return 0
        signatures = [self._signature(s) for s in self._steps]
        seen_blocks: list[list[str]] = []
        repeats = 0
        for i in range(len(signatures) - window + 1):
            block = signatures[i : i + window]
            for seen in seen_blocks:
                if block == seen:
                    repeats += 1
                    break
            else:
                seen_blocks.append(block)
        return repeats

    def tool_calls(self) -> list[str]:
        """Return ordered list of tool names called."""
        return [
            step.metadata.get("tool", step.content)
            for step in self._steps
            if step.step_type == "tool_call"
        ]


def loop_penalty(trajectory: Trajectory, window: int = 3, penalty_per_cycle: float = 0.15, cap: float = 0.60) -> float:
    """Compute a penalty score for detected loops.

    Returns 0.0 if no loops are detected, negative values (up to *-cap*)
    for repeated action cycles.
    """
    repeats = trajectory.loop_count(window=window)
    if repeats == 0:
        return 0.0
    return -min(repeats * penalty_per_cycle, cap)
