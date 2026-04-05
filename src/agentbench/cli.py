from __future__ import annotations

import argparse
from pathlib import Path

from agentbench import __version__
from agentbench.console import banner, dump_json, key_value_block, latest_summary_path, render_table
from agentbench.leaderboard import build_leaderboard, create_submission, save_submission, serve_leaderboard
from agentbench.runner import load_suite, prepare_task, render_summary_markdown, run_suite
from agentbench.scaffold import write_python_adapter_template
from agentbench.utils import read_json


DEFAULT_SUITE = Path("scenarios")
DEFAULT_SUITE_FALLBACK = Path("benchmarks/core.json")
DEFAULT_OUTPUT = Path("runs")
DEFAULT_SUBMISSIONS = Path("leaderboard/submissions")
DEFAULT_LEADERBOARD_SITE = Path("leaderboard/site")


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
    agent_group = run_parser.add_mutually_exclusive_group(required=True)
    agent_group.add_argument("--agent-command", help="Command template with placeholders like {task_file}.")
    agent_group.add_argument("--agent-exec", help="Executable or shell command prefix. AgentBench appends --task/--workspace/--result/--prompt automatically.")
    agent_group.add_argument("--agent-python", type=Path, help="Path to a Python adapter script with --task/--workspace/--result args.")
    agent_group.add_argument("--agent-docker-image", help="Docker image for an agent that accepts --task/--workspace/--result/--prompt.")
    run_parser.add_argument("--agent-docker-command", help="Optional command prefix to run inside the container before AgentBench appends standard flags.")
    run_parser.add_argument("--agent-docker-args", default="", help="Extra raw docker run arguments such as environment variables.")
    run_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    run_parser.add_argument("--task", help="Run only one task id.")
    run_parser.add_argument("--seed", type=int, action="append", dest="seeds")
    run_parser.add_argument("--repeat", type=int, default=1)
    run_parser.add_argument("--fail-fast", action="store_true")
    run_parser.add_argument("--json", action="store_true", help="Emit JSON summary.")
    run_parser.add_argument("--chaos", action="store_true", help="Enable chaos failure injection for supported scenarios.")
    run_parser.add_argument("--chaos-rate", type=float, default=0.15, help="Failure probability for chaos injection (default: 0.15).")
    run_parser.add_argument("--cost-model", default=None, help="Token pricing model name (e.g. gpt-4o, claude-sonnet-4).")
    run_parser.add_argument("-v", "--verbose", action="store_true", help="Include trajectory and cost details in console output.")

    prepare_parser = subparsers.add_parser("prepare", help="Materialize a single task episode for debugging or manual testing.")
    prepare_parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    prepare_parser.add_argument("--task", required=True)
    prepare_parser.add_argument("--seed", type=int, required=True)
    prepare_parser.add_argument("--output-dir", type=Path, default=Path("prepared"))
    prepare_parser.add_argument("--json", action="store_true")

    init_parser = subparsers.add_parser("init-adapter", help="Scaffold a Python adapter that can be wired to your agent.")
    init_parser.add_argument("--output", type=Path, required=True)

    report_parser = subparsers.add_parser("report", help="Render an existing summary.json.")
    report_parser.add_argument("--summary", type=Path)
    report_parser.add_argument("--json", action="store_true")

    submit_parser = subparsers.add_parser("submit", help="Validate and save a public leaderboard submission.")
    submit_parser.add_argument("--summary", type=Path, required=True)
    submit_parser.add_argument("--submissions-dir", type=Path, default=DEFAULT_SUBMISSIONS)
    submit_parser.add_argument("--agent-name", required=True)
    submit_parser.add_argument("--agent-version", required=True)
    submit_parser.add_argument("--organization", required=True)
    submit_parser.add_argument("--creator", required=True)
    submit_parser.add_argument("--framework", required=True)
    submit_parser.add_argument("--model", required=True)
    submit_parser.add_argument("--runtime", required=True)
    submit_parser.add_argument("--integration", required=True)
    submit_parser.add_argument("--website")
    submit_parser.add_argument("--source-url")
    submit_parser.add_argument("--verified", action="store_true")
    submit_parser.add_argument("--json", action="store_true")

    build_lb_parser = subparsers.add_parser("build-leaderboard", help="Build the public leaderboard site and JSON.")
    build_lb_parser.add_argument("--submissions-dir", type=Path, default=DEFAULT_SUBMISSIONS)
    build_lb_parser.add_argument("--output-dir", type=Path, default=DEFAULT_LEADERBOARD_SITE)
    build_lb_parser.add_argument("--json", action="store_true")

    serve_lb_parser = subparsers.add_parser("serve-leaderboard", help="Serve a dynamic leaderboard that refreshes from submissions.")
    serve_lb_parser.add_argument("--submissions-dir", type=Path, default=DEFAULT_SUBMISSIONS)
    serve_lb_parser.add_argument("--output-dir", type=Path, default=DEFAULT_LEADERBOARD_SITE)
    serve_lb_parser.add_argument("--host", default="127.0.0.1")
    serve_lb_parser.add_argument("--port", type=int, default=8765)

    return parser


def _resolve_suite(suite_arg: Path) -> Path:
    """Fall back to benchmarks/core.json if the scenarios/ directory doesn't exist."""
    if suite_arg.exists():
        return suite_arg
    if suite_arg == DEFAULT_SUITE and DEFAULT_SUITE_FALLBACK.exists():
        return DEFAULT_SUITE_FALLBACK
    return suite_arg  # let load_suite raise on missing


def cmd_list(args) -> int:
    suite = load_suite(_resolve_suite(args.suite))
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
    agent_command = build_agent_command(args)
    summary = run_suite(
        suite_path=_resolve_suite(args.suite),
        agent_command=agent_command,
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
        info = {
            "Suite": summary["suite"]["name"],
            "Episodes": summary["episodes"],
            "Passed": summary["passed"],
            "Failed": summary["failed"],
            "Average overall": summary["averages"].get("overall", 0.0),
            "Consistency": summary["consistency"] if summary["consistency"] is not None else "n/a",
            "Run dir": summary["run_dir"],
        }
        if "reliability" in summary.get("averages", {}):
            info["Average reliability"] = summary["averages"]["reliability"]
        # FinOps fields (only shown if agents reported costs)
        finops = summary.get("finops", {})
        if finops and finops.get("total_cost_usd") is not None:
            info["Total cost (USD)"] = f"${finops['total_cost_usd']:.6f}"
            info["Cost/success"] = f"${finops['cost_per_task_success']:.6f}" if finops.get("cost_per_task_success") is not None else "n/a"
            info["Efficiency score"] = finops.get("avg_efficiency_score", "n/a")
        print(key_value_block(info))
    return 0


def build_agent_command(args) -> str:
    if args.agent_exec is not None:
        return (
            f'{args.agent_exec} --task "{{task_file}}" --workspace "{{workspace}}" '
            f'--result "{{result_file}}" --prompt "{{prompt_file}}"'
        )
    if args.agent_python is not None:
        return (
            f'python "{args.agent_python}" --task {{task_file}} --workspace {{workspace}} '
            f'--result {{result_file}} --prompt {{prompt_file}}'
        )
    if args.agent_docker_image is not None:
        inner_command = args.agent_docker_command or ""
        prefix = f"{inner_command} " if inner_command else ""
        docker_args = f"{args.agent_docker_args} " if args.agent_docker_args else ""
        return (
            "docker run --rm "
            f'-v "{{docker_host_run_dir}}:{{docker_container_run_dir}}" '
            f'-v "{{docker_host_repo}}:{{docker_repo}}:ro" '
            f"{docker_args}"
            f'{args.agent_docker_image} '
            f'{prefix}'
            '--task "{docker_task_file}" --workspace "{docker_workspace}" '
            '--result "{docker_result_file}" --prompt "{docker_prompt_file}"'
        )
    return args.agent_command


def cmd_prepare(args) -> int:
    manifest = prepare_task(
        suite_path=_resolve_suite(args.suite),
        task_id=args.task,
        seed=args.seed,
        output_dir=args.output_dir,
    )
    if args.json:
        print(dump_json(manifest))
    else:
        print(banner("Omnionix AgentBench", "Task prepared"))
        print()
        print(key_value_block(
            {
                "Task": manifest["task_id"],
                "Seed": manifest["seed"],
                "Workspace": manifest["workspace"],
                "Task file": manifest["task_file"],
                "Prompt file": manifest["prompt_file"],
                "Result file": manifest["result_file"],
            }
        ))
    return 0


def cmd_init_adapter(args) -> int:
    output = write_python_adapter_template(args.output)
    print(banner("Omnionix AgentBench", "Python adapter scaffold created"))
    print()
    print(key_value_block({"Adapter": output}))
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


def cmd_submit(args) -> int:
    submission = create_submission(
        summary_path=args.summary,
        metadata={
            "agent": {
                "name": args.agent_name,
                "version": args.agent_version,
                "organization": args.organization,
                "creator": args.creator,
                "framework": args.framework,
                "model": args.model,
                "runtime": args.runtime,
                "integration": args.integration,
            },
            "links": {
                "website": args.website,
                "source_url": args.source_url,
            },
            "verified": args.verified,
        },
    )
    path = save_submission(submission, args.submissions_dir)
    if args.json:
        print(dump_json({"submission": submission, "path": str(path)}))
    else:
        print(banner("Omnionix AgentBench", "Submission saved"))
        print()
        print(key_value_block({"Agent": submission["agent"]["name"], "Submission": submission["submission_id"], "Path": path}))
    return 0


def cmd_build_leaderboard(args) -> int:
    output = build_leaderboard(args.submissions_dir, args.output_dir)
    if args.json:
        print(dump_json({"leaderboard_json": str(output), "site": str(args.output_dir / 'index.html')}))
    else:
        print(banner("Omnionix AgentBench", "Leaderboard built"))
        print()
        print(key_value_block({"JSON": output, "Site": args.output_dir / "index.html"}))
    return 0


def cmd_serve_leaderboard(args) -> int:
    print(banner("Omnionix AgentBench", f"Serving leaderboard on http://{args.host}:{args.port}"))
    serve_leaderboard(args.submissions_dir, args.output_dir, args.host, args.port)
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "list":
        return cmd_list(args)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "prepare":
        return cmd_prepare(args)
    if args.command == "init-adapter":
        return cmd_init_adapter(args)
    if args.command == "report":
        return cmd_report(args)
    if args.command == "submit":
        return cmd_submit(args)
    if args.command == "build-leaderboard":
        return cmd_build_leaderboard(args)
    if args.command == "serve-leaderboard":
        return cmd_serve_leaderboard(args)
    raise SystemExit(f"Unsupported command: {args.command}")
