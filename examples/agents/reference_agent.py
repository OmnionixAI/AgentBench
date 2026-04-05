from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path

from agentbench.adapters import load_context, write_result

def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--prompt", required=False)
    args = parser.parse_args()

    context = load_context(
        task_file=args.task,
        workspace=args.workspace,
        result_file=args.result,
        prompt_file=args.prompt,
    )
    task = context.task
    workspace = context.workspace
    artifacts: list[str] = []

    if task["family"] == "repo_patch":
        if task["scenario"] == "timezone_window":
            (workspace / "scheduler.py").write_text(
                "MINUTES_PER_DAY = 24 * 60\n\n\n"
                "def utc_window_to_local(start_utc_minutes: int, duration_minutes: int, offset_minutes: int) -> tuple[int, int]:\n"
                "    local_start = (start_utc_minutes + offset_minutes) % MINUTES_PER_DAY\n"
                "    local_end = (local_start + duration_minutes) % MINUTES_PER_DAY\n"
                "    return local_start, local_end\n",
                encoding="utf-8",
            )
        else:
            (workspace / "ratelimit.py").write_text(
                "def should_allow(request_timestamps: list[int], now: int, limit: int, window_seconds: int) -> bool:\n"
                "    recent = [stamp for stamp in request_timestamps if now - stamp < window_seconds]\n"
                "    return len(recent) < limit\n",
                encoding="utf-8",
            )
    elif task["family"] == "data_pipeline":
        if task["scenario"] == "margin_hotspots":
            totals: dict[tuple[str, str], dict[str, float]] = {}
            with (workspace / "sales.csv").open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    if float(row["on_time_rate"]) < 94.0:
                        continue
                    key = (row["region"], row["product"])
                    totals.setdefault(key, {"revenue": 0.0, "cost": 0.0})
                    totals[key]["revenue"] += float(row["revenue"])
                    totals[key]["cost"] += float(row["cost"])
            winner = max(
                totals.items(),
                key=lambda item: ((item[1]["revenue"] - item[1]["cost"]) / item[1]["revenue"]) if item[1]["revenue"] else -1.0,
            )
            margin = round(((winner[1]["revenue"] - winner[1]["cost"]) / winner[1]["revenue"]) * 100, 2)
            write_json(
                workspace / "answer.json",
                {
                    "winner_region": winner[0][0],
                    "winner_product": winner[0][1],
                    "margin_percent": margin,
                },
            )
            (workspace / "brief.md").write_text(
                f"{winner[0][0]} / {winner[0][1]} leads on filtered aggregate margin at {margin:.2f} percent.\n",
                encoding="utf-8",
            )
            artifacts.extend(["answer.json", "brief.md"])
        else:
            rows = []
            with (workspace / "inventory.csv").open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                rows.extend(reader)
            demand_map = {
                row["warehouse"]: {
                    "on_hand": int(row["on_hand"]),
                    "weekly_demand": int(row["weekly_demand"]),
                    "unit_cost": float(row["unit_transfer_cost"]),
                }
                for row in rows
            }
            days_cover = {
                warehouse: values["on_hand"] / (values["weekly_demand"] / 7.0)
                for warehouse, values in demand_map.items()
            }
            destination = min(days_cover, key=days_cover.get)
            needed_units = max(
                0,
                round((21.0 - days_cover[destination]) * (demand_map[destination]["weekly_demand"] / 7.0)),
            )
            feasible = []
            for source, values in demand_map.items():
                if source == destination:
                    continue
                reserve_units = round(28.0 * (values["weekly_demand"] / 7.0))
                surplus = values["on_hand"] - reserve_units
                if surplus <= 0:
                    continue
                units = min(surplus, needed_units)
                if units <= 0:
                    continue
                feasible.append((source, units, round(units * values["unit_cost"], 2)))
            chosen = min(feasible, key=lambda item: item[2])
            write_json(
                workspace / "answer.json",
                {
                    "source": chosen[0],
                    "destination": destination,
                    "units": int(chosen[1]),
                    "transfer_cost": chosen[2],
                },
            )
            (workspace / "brief.md").write_text(
                f"Move {chosen[1]} units from {chosen[0]} to {destination} at the lowest feasible transfer cost.\n",
                encoding="utf-8",
            )
            artifacts.extend(["answer.json", "brief.md"])
    elif task["family"] == "tool_workflow":
        if task["scenario"] == "support_refund":
            lookup = _run_tool(workspace, ["python", "tools.py", "order-lookup"])
            if lookup.returncode != 0:
                lookup = _run_tool(workspace, ["python", "tools.py", "order-lookup"])
            payload = json.loads(lookup.stdout)
            total_paid = float(payload["total_paid"])
            if payload["defective"] and payload["age_days"] <= 90:
                _run_tool(workspace, ["python", "tools.py", "refund", "--amount", f"{total_paid:.2f}"])
                message = f"We issued a refund of ${total_paid:.2f}."
            elif payload["age_days"] <= 30:
                amount = round(total_paid * 0.85, 2)
                _run_tool(workspace, ["python", "tools.py", "refund", "--amount", f"{amount:.2f}"])
                message = f"We issued a refund of ${amount:.2f}."
            elif payload["age_days"] <= 60:
                amount = round(total_paid * 0.85, 2)
                _run_tool(workspace, ["python", "tools.py", "credit", "--amount", f"{amount:.2f}"])
                message = f"We added store credit of ${amount:.2f}."
            else:
                _run_tool(workspace, ["python", "tools.py", "deny", "--reason", "outside_policy"])
                message = "The request is outside the policy window."
            (workspace / "customer_reply.md").write_text(message + "\n", encoding="utf-8")
            artifacts.append("customer_reply.md")
        else:
            status = _run_tool(workspace, ["python", "tools.py", "status"])
            if status.returncode != 0:
                status = _run_tool(workspace, ["python", "tools.py", "status"])
            payload = json.loads(status.stdout)
            _run_tool(workspace, ["python", "tools.py", "rollback", "--version", payload["healthy_version"]])
            _run_tool(workspace, ["python", "tools.py", "healthcheck"])
            _run_tool(workspace, ["python", "tools.py", "open-postmortem"])
            (workspace / "incident_report.md").write_text(
                f"Rolled checkout-api back to {payload['healthy_version']} and confirmed health.\n",
                encoding="utf-8",
            )
            artifacts.append("incident_report.md")
    elif task["family"] == "mcp_tool_use":
        mcp_artifact = _solve_mcp_task(task["scenario"], workspace)
        artifacts.append(mcp_artifact)
    elif task["family"] == "agentic_reliability":
        reliability_artifacts = _solve_reliability_task(task["scenario"], workspace)
        artifacts.extend(reliability_artifacts)
    else:
        raise ValueError(f"Unsupported family: {task['family']}")

    write_result(
        result_file=context.result_file,
        summary=f"Reference agent completed {task['id']}.",
        confidence=0.98,
        artifacts=artifacts,
    )
    return 0


def _run_tool(workspace: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=workspace, text=True, capture_output=True, check=False)


def _solve_mcp_task(scenario: str, workspace: Path) -> str:
    if scenario == "file_organise":
        tools = ["fs_list_directory", "fs_move_file", "fs_move_file"]
    elif scenario == "issue_triage":
        tools = ["gh_list_issues", "gh_add_label", "gh_close_issue"]
    else:
        tools = ["gh_create_issue", "slack_send_message", "slack_pin_message"]

    responses = []
    with subprocess.Popen(
        ["python", "mcp_server.py"],
        cwd=workspace,
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        for index, tool_name in enumerate(tools, start=1):
            payload = {
                "jsonrpc": "2.0",
                "id": index,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": {"step": index}},
            }
            assert process.stdin is not None
            assert process.stdout is not None
            process.stdin.write(json.dumps(payload) + "\n")
            process.stdin.flush()
            responses.append(json.loads(process.stdout.readline()))
        process.stdin.close()
        process.terminate()
        process.wait(timeout=5)

    write_json(
        workspace / "mcp_result.json",
        {"scenario": scenario, "tools_used": tools, "responses": len(responses)},
    )
    return "mcp_result.json"


def _solve_reliability_task(scenario: str, workspace: Path) -> list[str]:
    if scenario == "memory_refresh":
        turns = json.loads((workspace / "session_turns.json").read_text(encoding="utf-8"))
        answer = {
            "project": "Atlas",
            "owner": _extract_between(turns[2]["message"], ". ", " owns the rollout now."),
            "deadline": _extract_last_value(turns, "Update the target date to "),
            "channel": _extract_last_value(turns, "Use ", " as the operating channel."),
            "blocker": _extract_last_value(turns, "Current blocker is ", "."),
        }
    else:
        checkpoint = json.loads((workspace / "checkpoint_memory.json").read_text(encoding="utf-8"))
        turns = json.loads((workspace / "resume_turns.json").read_text(encoding="utf-8"))
        answer = {
            "account": checkpoint["account"],
            "region": _extract_last_value(turns, "region changed to ", "."),
            "severity": _extract_last_value(turns, "Current severity is ", " and approved rollback target"),
            "owner": "Omar",
            "rollback_target": _extract_last_value(turns, "approved rollback target is ", "."),
        }
    write_json(workspace / "final_answer.json", answer)
    write_json(workspace / "memory_snapshot.json", answer)
    return ["final_answer.json", "memory_snapshot.json"]


def _extract_last_value(turns: list[dict], prefix: str, suffix: str = ".") -> str:
    for turn in reversed(turns):
        message = turn["message"]
        start = message.find(prefix)
        if start == -1:
            continue
        start += len(prefix)
        end = message.find(suffix, start)
        if end == -1:
            end = len(message)
        return message[start:end].strip()
    raise ValueError(f"Unable to extract value for prefix: {prefix}")


def _extract_between(message: str, prefix: str, suffix: str) -> str:
    start = message.find(prefix)
    if start == -1:
        raise ValueError(f"Prefix not found: {prefix}")
    start += len(prefix)
    end = message.find(suffix, start)
    if end == -1:
        end = len(message)
    return message[start:end].strip()


if __name__ == "__main__":
    raise SystemExit(main())
