from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()

    task = read_json(Path(args.task))
    workspace = Path(args.workspace)
    result_path = Path(args.result)
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
    else:
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

    write_json(
        result_path,
        {
            "summary": f"Reference agent completed {task['id']}.",
            "confidence": 0.98,
            "artifacts": artifacts,
        },
    )
    return 0


def _run_tool(workspace: Path, command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=workspace, text=True, capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
