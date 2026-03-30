from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from agentbench.models import EpisodeResult, SuiteSpec
from agentbench.registry import get_family
from agentbench.scoring import consistency_score
from agentbench.utils import ensure_dir, read_json, sanitize_name, write_json


def load_suite(path: Path) -> SuiteSpec:
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
    per_task: list[dict] = []

    for result in results:
        for dimension, score in result.evaluation.scores.items():
            if score is not None:
                aggregates[dimension].append(float(score))
        aggregates["overall"].append(float(result.evaluation.overall))
        totals_by_task[result.task_id].append(float(result.evaluation.overall))
        per_task.append(
            {
                "task_id": result.task_id,
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
    return {
        "suite": {
            "name": suite.name,
            "version": suite.version,
            "description": suite.description,
            "source": str(suite_path),
            "weights": suite.weights,
        },
        "run_dir": str(run_dir),
        "episodes": len(results),
        "passed": sum(1 for result in results if result.evaluation.passed),
        "failed": sum(1 for result in results if not result.evaluation.passed),
        "averages": averages,
        "consistency": None if not consistency_values else round(sum(consistency_values) / len(consistency_values), 4),
        "tasks": per_task,
    }


def render_summary_markdown(summary: dict) -> str:
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
        "| Task | Seed | Passed | Overall | Success | Safety | Recovery | Efficiency | Calibration | Duration |",
        "| --- | ---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for task in summary["tasks"]:
        scores = task["scores"]
        lines.append(
            "| {task_id} | {seed} | {passed} | {overall} | {success} | {safety} | {recovery} | {efficiency} | {calibration} | {duration_seconds} |".format(
                task_id=task["task_id"],
                seed=task["seed"],
                passed="yes" if task["passed"] else "no",
                overall=task["overall"],
                success=_display_score(scores.get("success")),
                safety=_display_score(scores.get("safety")),
                recovery=_display_score(scores.get("recovery")),
                efficiency=_display_score(scores.get("efficiency")),
                calibration=_display_score(scores.get("calibration")),
                duration_seconds=task["duration_seconds"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def _display_score(value):
    return "n/a" if value is None else value


def _docker_mount_path(path: Path) -> str:
    return path.resolve().as_posix()
