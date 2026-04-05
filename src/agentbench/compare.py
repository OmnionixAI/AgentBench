from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentbench.utils import read_json


RUN_STAMP_RE = re.compile(r"^\d{8}-\d{6}$")
COMPARE_DIMENSIONS = [
    "overall",
    "success",
    "safety",
    "recovery",
    "efficiency",
    "calibration",
    "reliability",
    "consistency",
    "total_cost_usd",
    "cost_per_task_success",
    "avg_efficiency_score",
]


@dataclass
class DimensionDelta:
    dimension: str
    baseline: float | None
    current: float | None
    delta: float | None
    regressed: bool


@dataclass
class RunComparison:
    baseline_run_dir: str
    current_run_dir: str
    baseline_timestamp: str
    current_timestamp: str
    deltas: list[DimensionDelta]
    any_regression: bool
    regression_threshold: float
    regression_count: int
    baseline_episodes: int
    current_episodes: int

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["deltas"] = [asdict(delta) for delta in self.deltas]
        return payload


def compare_runs(baseline: Path, current: Path, threshold: float = 0.05) -> RunComparison:
    baseline_summary_path, baseline_summary = load_summary_payload(baseline)
    current_summary_path, current_summary = load_summary_payload(current)

    deltas: list[DimensionDelta] = []
    for dimension in _dimensions_for(baseline_summary, current_summary):
        baseline_value = _summary_value(baseline_summary, dimension)
        current_value = _summary_value(current_summary, dimension)
        delta = None if baseline_value is None or current_value is None else round(current_value - baseline_value, 4)
        regressed = bool(delta is not None and delta < 0 and abs(delta) >= threshold)
        deltas.append(
            DimensionDelta(
                dimension=dimension,
                baseline=baseline_value,
                current=current_value,
                delta=delta,
                regressed=regressed,
            )
        )

    regression_count = sum(1 for delta in deltas if delta.regressed)
    return RunComparison(
        baseline_run_dir=str(_run_dir_from_summary(baseline_summary_path, baseline_summary)),
        current_run_dir=str(_run_dir_from_summary(current_summary_path, current_summary)),
        baseline_timestamp=_timestamp_for_summary(baseline_summary_path, baseline_summary),
        current_timestamp=_timestamp_for_summary(current_summary_path, current_summary),
        deltas=deltas,
        any_regression=regression_count > 0,
        regression_threshold=threshold,
        regression_count=regression_count,
        baseline_episodes=int(baseline_summary.get("episodes", 0)),
        current_episodes=int(current_summary.get("episodes", 0)),
    )


def load_summary_payload(path: Path) -> tuple[Path, dict[str, Any]]:
    summary_path = resolve_summary_path(path)
    payload = read_json(summary_path)
    return summary_path, payload


def resolve_summary_path(path: Path) -> Path:
    candidate = path
    if candidate.is_file():
        if candidate.name != "summary.json":
            raise FileNotFoundError(f"Expected summary.json, got: {candidate}")
        return candidate
    summary = candidate / "summary.json"
    if summary.exists():
        return summary
    raise FileNotFoundError(f"Could not find summary.json under: {candidate}")


def resolve_window_baseline(output_root: Path, window: int, current: Path | None = None) -> Path:
    if window < 1:
        raise ValueError("--window must be at least 1.")
    runs = list_recent_runs(output_root)
    if len(runs) <= window:
        raise ValueError(f"Not enough completed runs in {output_root} to look back {window} run(s).")
    current_path = current if current is not None else output_root / "latest"
    current_summary = resolve_summary_path(current_path)
    current_run_dir = _run_dir_from_summary(current_summary, read_json(current_summary))
    filtered_runs = [run for run in runs if run.resolve() != current_run_dir.resolve()]
    if len(filtered_runs) < window:
        raise ValueError(f"Not enough historical runs in {output_root} after excluding current run.")
    return filtered_runs[window - 1]


def list_recent_runs(output_root: Path) -> list[Path]:
    if not output_root.exists():
        return []
    runs = [
        path for path in output_root.iterdir()
        if path.is_dir() and RUN_STAMP_RE.match(path.name) and (path / "summary.json").exists()
    ]
    return sorted(runs, key=lambda path: path.name, reverse=True)


def render_comparison_markdown(comparison: RunComparison) -> str:
    lines = [
        "# AgentBench Cross-Run Comparison",
        "",
        f"- Baseline: {comparison.baseline_timestamp} ({comparison.baseline_episodes} episodes)",
        f"- Current: {comparison.current_timestamp} ({comparison.current_episodes} episodes)",
        f"- Threshold: {comparison.regression_threshold}",
        "",
        "| Dimension | Baseline | Current | Delta | Flag |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for delta in comparison.deltas:
        lines.append(
            "| {dimension} | {baseline} | {current} | {delta_value} | {flag} |".format(
                dimension=delta.dimension,
                baseline=_display(delta.baseline),
                current=_display(delta.current),
                delta_value=_display_delta(delta.delta),
                flag="REGRESSION" if delta.regressed else "",
            )
        )
    lines.extend(
        [
            "",
            f"RESULT: {comparison.regression_count} regressions detected (threshold={comparison.regression_threshold})",
        ]
    )
    return "\n".join(lines)


def _dimensions_for(baseline_summary: dict[str, Any], current_summary: dict[str, Any]) -> list[str]:
    discovered = []
    for dimension in COMPARE_DIMENSIONS:
        if _summary_value(baseline_summary, dimension) is not None or _summary_value(current_summary, dimension) is not None:
            discovered.append(dimension)

    additional = sorted(
        (
            set(baseline_summary.get("averages", {}))
            | set(current_summary.get("averages", {}))
        ) - set(discovered)
    )
    return discovered + additional


def _summary_value(summary: dict[str, Any], dimension: str) -> float | None:
    if dimension == "consistency":
        value = summary.get("consistency")
    elif dimension in {"total_cost_usd", "cost_per_task_success", "avg_efficiency_score"}:
        value = summary.get("finops", {}).get(dimension)
    else:
        value = summary.get("averages", {}).get(dimension)
    return None if value is None else round(float(value), 4)


def _run_dir_from_summary(summary_path: Path, summary: dict[str, Any]) -> Path:
    run_dir = summary.get("run_dir")
    if run_dir:
        return Path(run_dir)
    return summary_path.parent


def _timestamp_for_summary(summary_path: Path, summary: dict[str, Any]) -> str:
    run_dir = _run_dir_from_summary(summary_path, summary)
    if RUN_STAMP_RE.match(run_dir.name):
        parsed = datetime.strptime(run_dir.name, "%Y%m%d-%H%M%S").replace(tzinfo=UTC)
        return parsed.isoformat().replace("+00:00", "Z")
    modified = datetime.fromtimestamp(summary_path.stat().st_mtime, tz=UTC)
    return modified.isoformat().replace("+00:00", "Z")


def _display(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"


def _display_delta(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.4f}"
