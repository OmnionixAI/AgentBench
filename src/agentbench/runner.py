from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from agentbench import __version__
from agentbench.finops import compute_cost, cost_per_task_success, efficiency_score, parse_token_report
from agentbench.models import EpisodeResult, SuiteSpec
from agentbench.registry import get_family
from agentbench.scoring import consistency_score
from agentbench.trajectory import Trajectory
from agentbench.utils import ensure_dir, read_json, sanitize_name, stable_hash, write_json


def load_suite(path: Path) -> SuiteSpec:
    """Load a suite from JSON, YAML, or a directory of scenario files."""
    if path.is_dir() or path.suffix in (".yaml", ".yml"):
        from agentbench.scenario_loader import load_auto
        return load_auto(path)
    return SuiteSpec.from_dict(read_json(path))


def expand_tasks(suite: SuiteSpec, task_filter: str | None, explicit_seeds: list[int] | None) -> list[tuple]:
    selected = [task for task in suite.tasks if task_filter is None or task.id == task_filter]
    episodes: list[tuple] = []
    for task in selected:
        seeds = explicit_seeds if explicit_seeds else task.default_seeds
        for seed in seeds:
            episodes.append((task, int(seed)))
    return episodes


def find_task(suite: SuiteSpec, task_id: str):
    for task in suite.tasks:
        if task.id == task_id:
            return task
    raise KeyError(f"Unknown task id: {task_id}")


def _link_latest(output_root: Path, run_dir: Path) -> None:
    latest = output_root / "latest"
    if latest.exists() or latest.is_symlink():
        if latest.is_dir() and not latest.is_symlink():
            shutil.rmtree(latest)
        else:
            latest.unlink()
    if os.name == "nt":
        shutil.copytree(run_dir, latest)
    else:
        latest.symlink_to(run_dir, target_is_directory=True)


def _format_command(template: str, prepared, run_dir: Path) -> str:
    docker_container_run_dir = "/agentbench_run"
    docker_repo_dir = "/agentbench_host_repo"
    values = {
        "task_file": str(prepared.task_file),
        "prompt_file": str(prepared.prompt_path),
        "workspace": str(prepared.workspace),
        "result_file": str(prepared.result_file),
        "run_dir": str(run_dir),
        "docker_host_run_dir": _docker_mount_path(run_dir),
        "docker_container_run_dir": docker_container_run_dir,
        "docker_task_file": f"{docker_container_run_dir}/task.json",
        "docker_prompt_file": f"{docker_container_run_dir}/prompt.md",
        "docker_workspace": f"{docker_container_run_dir}/workspace",
        "docker_result_file": f"{docker_container_run_dir}/workspace/agent_result.json",
        "docker_host_repo": _docker_mount_path(Path.cwd()),
        "docker_repo": docker_repo_dir,
    }
    return template.format(**values)


def _agent_env(prepared, run_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "AGENTBENCH_TASK_FILE": str(prepared.task_file),
            "AGENTBENCH_PROMPT_FILE": str(prepared.prompt_path),
            "AGENTBENCH_WORKSPACE": str(prepared.workspace),
            "AGENTBENCH_RESULT_FILE": str(prepared.result_file),
            "AGENTBENCH_RUN_DIR": str(run_dir),
        }
    )
    return env


def run_suite(
    suite_path: Path,
    agent_command: str,
    output_root: Path,
    task_filter: str | None = None,
    explicit_seeds: list[int] | None = None,
    repeat: int = 1,
    fail_fast: bool = False,
) -> dict:
    suite = load_suite(suite_path)
    run_stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    run_dir = ensure_dir(output_root / run_stamp)
    episodes = expand_tasks(suite, task_filter, explicit_seeds)
    results: list[EpisodeResult] = []

    for task, seed in episodes:
        for iteration in range(1, repeat + 1):
            label = f"{task.id}-seed{seed}-run{iteration}"
            episode_dir = ensure_dir(run_dir / sanitize_name(label))
            family = get_family(task.family)
            prepared = family.prepare(task, seed, episode_dir)
            stdout_path = episode_dir / "agent_stdout.txt"
            stderr_path = episode_dir / "agent_stderr.txt"
            command = _format_command(agent_command, prepared, episode_dir)
            start = time.perf_counter()
            completed = subprocess.run(
                command,
                shell=True,
                cwd=Path.cwd(),
                env=_agent_env(prepared, episode_dir),
                text=True,
                capture_output=True,
            )
            duration = time.perf_counter() - start
            stdout_path.write_text(completed.stdout, encoding="utf-8")
            stderr_path.write_text(completed.stderr, encoding="utf-8")

            # --- Trajectory tracking (best-effort) ---
            trajectory = Trajectory()
            trajectory.add("start", f"Starting {task.id} seed={seed} run={iteration}")
            for line in completed.stdout.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("[THOUGHT]"):
                    trajectory.add("thought", stripped[9:].strip())
                elif stripped.startswith("[TOOL_CALL]"):
                    trajectory.add("tool_call", stripped[11:].strip())
                elif stripped.startswith("[OBSERVATION]"):
                    trajectory.add("observation", stripped[13:].strip())
                elif stripped.startswith("[ERROR]"):
                    trajectory.add("error", stripped[7:].strip())
                else:
                    trajectory.add("observation", stripped)
            trajectory.add("finish", f"exit_code={completed.returncode} duration={duration:.2f}s")
            write_json(episode_dir / "trajectory.json", trajectory.to_list())

            # --- FinOps: parse optional token report ---
            token_report = parse_token_report(
                workspace=prepared.workspace,
                stdout=completed.stdout,
            )
            episode_cost: float | None = None
            if token_report is not None:
                episode_cost = compute_cost(token_report)

            evaluation = family.evaluate(
                prepared=prepared,
                suite_weights=suite.weights,
                duration_seconds=duration,
                exit_code=completed.returncode,
            )
            write_json(
                episode_dir / "evaluation.json",
                {
                    "task_id": task.id,
                    "seed": seed,
                    "run": iteration,
                    "duration_seconds": round(duration, 4),
                    "exit_code": completed.returncode,
                    "scores": evaluation.scores,
                    "overall": round(evaluation.overall, 4),
                    "passed": evaluation.passed,
                    "notes": evaluation.notes,
                    "details": evaluation.details,
                    "cost_usd": episode_cost,
                },
            )
            results.append(
                EpisodeResult(
                    task_id=task.id,
                    seed=seed,
                    run_label=label,
                    workspace=prepared.workspace,
                    duration_seconds=duration,
                    exit_code=completed.returncode,
                    stdout_path=stdout_path,
                    stderr_path=stderr_path,
                    evaluation=evaluation,
                    trajectory=trajectory.to_list(),
                    cost_usd=episode_cost,
                )
            )
            if fail_fast and not evaluation.passed:
                break
        if fail_fast and results and not results[-1].evaluation.passed:
            break

    summary = build_summary(suite, suite_path, run_dir, results)
    write_json(run_dir / "summary.json", summary)
    (run_dir / "summary.md").write_text(render_summary_markdown(summary), encoding="utf-8")
    _link_latest(output_root, run_dir)
    return summary


def prepare_task(suite_path: Path, task_id: str, seed: int, output_dir: Path) -> dict:
    suite = load_suite(suite_path)
    task = find_task(suite, task_id)
    prepared_root = ensure_dir(output_dir / sanitize_name(f"{task.id}-seed{seed}"))
    family = get_family(task.family)
    prepared = family.prepare(task, seed, prepared_root)
    manifest = {
        "suite": suite.name,
        "task_id": task.id,
        "seed": seed,
        "workspace": str(prepared.workspace),
        "task_file": str(prepared.task_file),
        "prompt_file": str(prepared.prompt_path),
        "result_file": str(prepared.result_file),
    }
    write_json(prepared_root / "prepared.json", manifest)
    return manifest


def build_summary(suite: SuiteSpec, suite_path: Path, run_dir: Path, results: list[EpisodeResult]) -> dict:
    aggregates: dict[str, list[float]] = defaultdict(list)
    totals_by_task: dict[str, list[float]] = defaultdict(list)
    task_family_map = {task.id: task.family for task in suite.tasks}
    task_tags_map = {task.id: task.tags for task in suite.tasks}
    family_totals: dict[str, list[float]] = defaultdict(list)
    tag_totals: dict[str, list[float]] = defaultdict(list)
    per_task: list[dict] = []
    total_cost = 0.0
    costs_available = False

    for result in results:
        for dimension, score in result.evaluation.scores.items():
            if score is not None:
                aggregates[dimension].append(float(score))
        aggregates["overall"].append(float(result.evaluation.overall))
        totals_by_task[result.task_id].append(float(result.evaluation.overall))
        family_totals[task_family_map.get(result.task_id, "unknown")].append(float(result.evaluation.overall))
        for tag in task_tags_map.get(result.task_id, []):
            tag_totals[tag].append(float(result.evaluation.overall))
        if result.cost_usd is not None:
            total_cost += result.cost_usd
            costs_available = True
        per_task.append(
            {
                "task_id": result.task_id,
                "family": task_family_map.get(result.task_id, "unknown"),
                "seed": result.seed,
                "run_label": result.run_label,
                "passed": result.evaluation.passed,
                "overall": round(result.evaluation.overall, 4),
                "scores": {
                    key: None if value is None else round(value, 4)
                    for key, value in result.evaluation.scores.items()
                },
                "duration_seconds": round(result.duration_seconds, 4),
                "exit_code": result.exit_code,
                "workspace": str(result.workspace),
                "stdout_path": str(result.stdout_path),
                "stderr_path": str(result.stderr_path),
                "cost_usd": result.cost_usd,
            }
        )

    averages = {
        key: round(sum(values) / len(values), 4)
        for key, values in aggregates.items()
        if values
    }
    consistency_values = [
        value for value in (consistency_score(series) for series in totals_by_task.values()) if value is not None
    ]

    # FinOps summary fields
    passed_count = sum(1 for result in results if result.evaluation.passed)
    finops: dict[str, float | None] = {
        "total_cost_usd": round(total_cost, 6) if costs_available else None,
        "cost_per_task_success": round(cost_per_task_success(total_cost, passed_count), 6) if costs_available else None,
        "avg_efficiency_score": None,
    }
    if costs_available and results:
        avg_overall = averages.get("overall", 0.0)
        avg_duration = sum(r.duration_seconds for r in results) / len(results)
        avg_cost = total_cost / len(results) if len(results) > 0 else 0.0001
        finops["avg_efficiency_score"] = efficiency_score(avg_overall, avg_cost, avg_duration)

    by_family = {
        family: {
            "average_overall": round(sum(values) / len(values), 4),
            "episodes": len(values),
        }
        for family, values in family_totals.items()
        if values
    }
    by_tag = {
        tag: {
            "average_overall": round(sum(values) / len(values), 4),
            "episodes": len(values),
        }
        for tag, values in tag_totals.items()
        if values
    }

    suite_fingerprint = stable_hash(
        {
            "suite_name": suite.name,
            "suite_version": suite.version,
            "weights": suite.weights,
            "tasks": [
                {
                    "id": task.id,
                    "family": task.family,
                    "scenario": task.scenario,
                    "difficulty": task.difficulty,
                    "default_seeds": task.default_seeds,
                }
                for task in suite.tasks
            ],
        }
    )

    return {
        "suite": {
            "name": suite.name,
            "version": suite.version,
            "description": suite.description,
            "source": str(suite_path),
            "weights": suite.weights,
            "fingerprint": suite_fingerprint,
        },
        "agentbench_version": __version__,
        "run_dir": str(run_dir),
        "episodes": len(results),
        "passed": passed_count,
        "failed": sum(1 for result in results if not result.evaluation.passed),
        "averages": averages,
        "consistency": None if not consistency_values else round(sum(consistency_values) / len(consistency_values), 4),
        "by_family": by_family,
        "by_tag": by_tag,
        "finops": finops,
        "tasks": per_task,
    }


def render_summary_markdown(summary: dict) -> str:
    dimensions = list(summary["suite"]["weights"].keys())
    dimension_headers = [dimension.replace("_", " ").title() for dimension in dimensions]
    lines = [
        f"# {summary['suite']['name']}",
        "",
        summary["suite"]["description"],
        "",
        "## Aggregate",
        "",
        f"- Episodes: {summary['episodes']}",
        f"- Passed: {summary['passed']}",
        f"- Failed: {summary['failed']}",
        f"- Average overall: {summary['averages'].get('overall', 0.0)}",
        f"- Consistency: {summary['consistency'] if summary['consistency'] is not None else 'n/a'}",
        "",
        "## Task Results",
        "",
        "| Task | Seed | Passed | Overall | " + " | ".join(dimension_headers) + " | Duration |",
        "| --- | ---: | :---: | ---: | " + " | ".join("---:" for _ in dimension_headers) + " | ---: |",
    ]
    for task in summary["tasks"]:
        scores = task["scores"]
        rendered_dimensions = [_display_score(scores.get(dimension)) for dimension in dimensions]
        lines.append(
            "| {task_id} | {seed} | {passed} | {overall} | {dimensions} | {duration_seconds} |".format(
                task_id=task["task_id"],
                seed=task["seed"],
                passed="yes" if task["passed"] else "no",
                overall=task["overall"],
                dimensions=" | ".join(str(value) for value in rendered_dimensions),
                duration_seconds=task["duration_seconds"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def _display_score(value):
    return "n/a" if value is None else value


def _docker_mount_path(path: Path) -> str:
    return path.resolve().as_posix()
