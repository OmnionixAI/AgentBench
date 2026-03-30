"""FinOps — token-to-USD cost tracking and efficiency scoring.

AgentBench does not call any LLM itself.  Cost tracking is opt-in:
the agent under test reports its own token usage back to the harness
via either a ``token_report.json`` file in the workspace or by
emitting ``[AGENTBENCH_TOKENS]`` markers in its stdout.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# Reference prices per 1K tokens (USD, as of early 2026).
# Users can override via --cost-model or by passing price_overrides.
TOKEN_PRICES: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4.1": {"input": 0.002, "output": 0.008},
    "gpt-4.1-mini": {"input": 0.0004, "output": 0.0016},
    "gpt-4.1-nano": {"input": 0.0001, "output": 0.0004},
    "o3": {"input": 0.002, "output": 0.008},
    "o4-mini": {"input": 0.00011, "output": 0.00044},
    "claude-sonnet-4": {"input": 0.003, "output": 0.015},
    "claude-opus-4": {"input": 0.015, "output": 0.075},
    "claude-haiku-3.5": {"input": 0.0008, "output": 0.004},
    "gemini-2.5-pro": {"input": 0.00125, "output": 0.01},
    "gemini-2.5-flash": {"input": 0.00015, "output": 0.0006},
    "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
    "deepseek-v3": {"input": 0.00014, "output": 0.00028},
    "deepseek-r1": {"input": 0.00055, "output": 0.00219},
}


_TOKEN_MARKER_RE = re.compile(
    r"\[AGENTBENCH_TOKENS\]\s*(\{.*?\})\s*\[/AGENTBENCH_TOKENS\]",
    re.DOTALL,
)


def parse_token_report(
    workspace: Path | None = None,
    stdout: str | None = None,
) -> dict[str, Any] | None:
    """Attempt to extract a token usage report from the agent.

    Checks (in order):
    1. ``workspace/token_report.json``
    2. ``[AGENTBENCH_TOKENS]{...}[/AGENTBENCH_TOKENS]`` markers in *stdout*

    Returns a dict with ``model``, ``input_tokens``, ``output_tokens`` keys,
    or ``None`` if the agent did not report anything.
    """
    # 1. Try workspace file
    if workspace is not None:
        report_path = workspace / "token_report.json"
        if report_path.exists():
            try:
                data = json.loads(report_path.read_text(encoding="utf-8"))
                if _valid_report(data):
                    return _normalise(data)
            except (json.JSONDecodeError, KeyError):
                pass

    # 2. Try stdout markers
    if stdout:
        match = _TOKEN_MARKER_RE.search(stdout)
        if match:
            try:
                data = json.loads(match.group(1))
                if _valid_report(data):
                    return _normalise(data)
            except (json.JSONDecodeError, KeyError):
                pass

    return None


def _valid_report(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    return "input_tokens" in data and "output_tokens" in data


def _normalise(data: dict) -> dict[str, Any]:
    return {
        "model": str(data.get("model", "unknown")),
        "input_tokens": int(data["input_tokens"]),
        "output_tokens": int(data["output_tokens"]),
    }


def compute_cost(
    report: dict[str, Any],
    price_overrides: dict[str, dict[str, float]] | None = None,
) -> float:
    """Compute USD cost from a token report."""
    prices = price_overrides or TOKEN_PRICES
    model = report.get("model", "unknown")
    model_prices = prices.get(model, prices.get("gpt-4o", {"input": 0.0025, "output": 0.010}))
    input_cost = (report.get("input_tokens", 0) / 1000.0) * model_prices["input"]
    output_cost = (report.get("output_tokens", 0) / 1000.0) * model_prices["output"]
    return round(input_cost + output_cost, 6)


def cost_per_task_success(total_cost: float, tasks_passed: int) -> float:
    """Cost per successfully completed task."""
    if tasks_passed <= 0:
        return float("inf") if total_cost > 0 else 0.0
    return round(total_cost / tasks_passed, 6)


def efficiency_score(
    accuracy: float,
    cost_usd: float,
    latency_seconds: float,
    ceiling: float = 100.0,
) -> float:
    """Compute efficiency: Accuracy / (Cost × Latency), normalised to [0, 1].

    Parameters
    ----------
    accuracy : float
        Overall accuracy score in [0, 1].
    cost_usd : float
        Total USD cost.
    latency_seconds : float
        Total execution time.
    ceiling : float
        Raw score ceiling for normalisation.

    Returns
    -------
    float
        Normalised efficiency score in [0, 1].
    """
    denominator = max(cost_usd, 0.0001) * max(latency_seconds, 0.1)
    raw = accuracy / denominator
    return round(min(raw / ceiling, 1.0), 4)
