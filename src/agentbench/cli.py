from __future__ import annotations

import argparse
from pathlib import Path

from agentbench import __version__
from agentbench.console import banner, dump_json, key_value_block, latest_summary_path, render_table
from agentbench.runner import load_suite, render_summary_markdown, run_suite
from agentbench.utils import read_json


DEFAULT_SUITE = Path("benchmarks/core.json")
DEFAULT_OUTPUT = Path("runs")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentbench",
        description="Omnionix AgentBench: benchmark real AI agents on dynamic, seeded workflows.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List benchmark tasks.")
    list_parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    list_parser.add_argument("--json", action="store_true")

    run_parser = subparsers.add_parser("run", help="Run the benchmark suite against an agent command.")
    run_parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    run_parser.add_argument("--agent-command", required=True, help="Command template with placeholders like {task_file}.")
    run_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--task", help="Run only one task id.")
    run_parser.add_argument("--seed", type=int, action="append", dest="seeds")
    run_parser.add_argument("--repeat", type=int, default=1)
    run_parser.add_argument("--fail-fast", action="store_true")
    run_parser.add_argument("--json", action="store_true", help="Emit JSON summary.")

    report_parser = subparsers.add_parser("report", help="Render an existing summary.json.")
    report_parser.add_argument("--summary", type=Path)
    report_parser.add_argument("--json", action="store_true")

    return parser


def cmd_list(args) -> int:
    suite = load_suite(args.suite)
    payload = {
        "suite": suite.name,
        "version": suite.version,
        "description": suite.description,
        "tasks": [
            {
                "id": task.id,
                "family": task.family,
                "difficulty": task.difficulty,
                "default_seeds": task.default_seeds,
                "tags": task.tags,
            }
            for task in suite.tasks
        ],
    }
    if args.json:
        print(dump_json(payload))
        return 0

    print(banner("Omnionix AgentBench", f"{suite.name} v{suite.version}"))
    print()
    print(key_value_block({"Description": suite.description, "Tasks": len(suite.tasks)}))
    print()
    rows = [
        [task.id, task.family, task.difficulty, ",".join(map(str, task.default_seeds)), ",".join(task.tags)]
        for task in suite.tasks
    ]
    print(render_table(["ID", "Family", "Difficulty", "Seeds", "Tags"], rows))
    return 0


def cmd_run(args) -> int:
    summary = run_suite(
        suite_path=args.suite,
        agent_command=args.agent_command,
        output_root=args.output_dir,
        task_filter=args.task,
        explicit_seeds=args.seeds,
        repeat=args.repeat,
        fail_fast=args.fail_fast,
    )
    if args.json:
        print(dump_json(summary))
    else:
        print(banner("Omnionix AgentBench", "Run complete"))
        print()
        print(
            key_value_block(
                {
                    "Suite": summary["suite"]["name"],
                    "Episodes": summary["episodes"],
                    "Passed": summary["passed"],
                    "Failed": summary["failed"],
                    "Average overall": summary["averages"].get("overall", 0.0),
                    "Consistency": summary["consistency"] if summary["consistency"] is not None else "n/a",
                    "Run dir": summary["run_dir"],
                }
            )
        )
    return 0


def cmd_report(args) -> int:
    summary_path = args.summary
    if summary_path is None:
        summary_path = latest_summary_path(DEFAULT_OUTPUT)
        if summary_path is None:
            raise SystemExit("No summary found. Run the benchmark first or pass --summary.")
    payload = read_json(summary_path)
    if args.json:
        print(dump_json(payload))
    else:
        print(render_summary_markdown(payload))
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "list":
        return cmd_list(args)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "report":
        return cmd_report(args)
    raise SystemExit(f"Unsupported command: {args.command}")
