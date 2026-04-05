"""MCP Tool Use task family."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from agentbench.chaos import chaos_recovery_score
from agentbench.families.base import TaskFamily
from agentbench.metrics.entropy import tool_selection_entropy
from agentbench.mock_servers.decoys import generate_decoy_tools
from agentbench.mock_servers.filesystem import FilesystemServer
from agentbench.mock_servers.github import GitHubServer
from agentbench.mock_servers.slack import SlackServer
from agentbench.models import Evaluation, PreparedTask, TaskSpec
from agentbench.scoring import calibration_score, ratio_with_budget, weighted_score
from agentbench.trajectory import Trajectory, loop_penalty
from agentbench.transport.protocol import MCPToolRegistry
from agentbench.utils import ensure_dir, read_json, write_json


# Tools that are actually correct for each scenario
_CORRECT_TOOLS: dict[str, set[str]] = {
    "file_organise": {
        "fs_read_file", "fs_write_file", "fs_list_directory", "fs_move_file",
        "fs_delete_file", "fs_search_files", "fs_copy_file", "fs_mkdir",
    },
    "issue_triage": {
        "gh_list_issues", "gh_add_label", "gh_assign_reviewer", "gh_close_issue",
        "gh_create_issue", "gh_get_repo", "gh_list_repos",
    },
    "incident_notify": {
        "slack_send_message", "slack_list_channels", "slack_create_channel",
        "slack_set_topic", "slack_list_users", "slack_pin_message",
        "gh_list_issues", "gh_create_issue",
    },
}


class MCPToolUseFamily(TaskFamily):
    def prepare(self, spec: TaskSpec, seed: int, run_root: Path) -> PreparedTask:
        workspace = ensure_dir(run_root / "workspace")
        prompt_path = run_root / "prompt.md"
        task_file = run_root / "task.json"
        result_file = workspace / "agent_result.json"
        internal = ensure_dir(workspace / ".agentbench_internal")

        # Build composite registry with all three servers + decoys
        registry = MCPToolRegistry()
        fs = FilesystemServer()
        gh = GitHubServer(seed=seed)
        sl = SlackServer(seed=seed)
        fs.register(registry)
        gh.register(registry)
        sl.register(registry)
        decoy_names = generate_decoy_tools(registry)

        # Write the tool manifest so the agent knows what's available
        write_json(workspace / "mcp_manifest.json", {"tools": registry.manifest()})
        total_tools = len(registry.list_tools())

        # Determine scenario
        if spec.scenario == "file_organise":
            expected = self._setup_file_organise(workspace, internal, fs, seed)
            overview = (
                "Use the MCP tool server to organise files in the virtual filesystem. "
                "Read the task description, move files to the correct directories, and clean up."
            )
        elif spec.scenario == "issue_triage":
            expected = self._setup_issue_triage(workspace, internal, gh, seed)
            overview = (
                "Use the MCP tool server to triage GitHub issues: label, assign, and close "
                "resolved issues according to the triage rules."
            )
        elif spec.scenario == "incident_notify":
            expected = self._setup_incident_notify(workspace, internal, gh, sl, seed)
            overview = (
                "Use the MCP tool server to handle an incident: create a GitHub issue, "
                "notify the on-call channel in Slack, and pin the notification."
            )
        else:
            raise ValueError(f"Unsupported MCP scenario: {spec.scenario}")

        # Write the MCP server script into the workspace
        (workspace / "mcp_server.py").write_text(
            _mcp_server_script(), encoding="utf-8"
        )

        deliverables = [
            "Interact with the MCP server via `python mcp_server.py` (stdio transport).",
            "Complete the task objective described in the prompt.",
            "Write agent_result.json with summary, confidence, and artifacts.",
        ]
        rules = [
            "Use only the tools listed in mcp_manifest.json.",
            "Do not manually edit files under .agentbench_internal/.",
            "Recover from any transient tool failures by retrying.",
        ]

        prompt_path.write_text(self.make_prompt(spec.title, overview, rules, deliverables), encoding="utf-8")

        write_json(task_file, {
            **self.public_task_manifest(spec, seed, deliverables, rules),
            "mcp_transport": "stdio",
            "mcp_command": "python mcp_server.py",
            "total_tools": total_tools,
        })

        # Store internal state for evaluation
        state = {
            "scenario": spec.scenario,
            "expected": expected,
            "total_tools": total_tools,
            "correct_tools": sorted(_CORRECT_TOOLS.get(spec.scenario, set())),
            "decoy_tools": sorted(decoy_names),
            "completed": False,
        }
        if spec.scenario == "file_organise":
            state["files_moved"] = 0
        elif spec.scenario == "issue_triage":
            state["labels_applied"] = 0
            state["issues_closed"] = 0
        elif spec.scenario == "incident_notify":
            state["issue_created"] = False
            state["slack_notified"] = False
            state["message_pinned"] = False
        write_json(internal / "state.json", state)
        (internal / "tool_log.json").write_text("[]", encoding="utf-8")

        return PreparedTask(
            spec=spec,
            seed=seed,
            workspace=workspace,
            prompt_path=prompt_path,
            task_file=task_file,
            result_file=result_file,
            metadata={
                "expected": expected,
                "total_tools": total_tools,
                "correct_tools": _CORRECT_TOOLS.get(spec.scenario, set()),
            },
        )

    def evaluate(
        self,
        prepared: PreparedTask,
        suite_weights: dict[str, float],
        duration_seconds: float,
        exit_code: int,
    ) -> Evaluation:
        internal = prepared.workspace / ".agentbench_internal"
        state = read_json(internal / "state.json")
        tool_log = _read_json_safe(internal / "tool_log.json", [])
        agent_result = _read_json_safe(prepared.result_file, {})
        expected = state.get("expected", {})

        # --- Success scoring (scenario-specific) ---
        if prepared.spec.scenario == "file_organise":
            success = self._score_file_organise(state)
        elif prepared.spec.scenario == "issue_triage":
            success = self._score_issue_triage(state)
        elif prepared.spec.scenario == "incident_notify":
            success = self._score_incident_notify(state)
        else:
            success = 0.0

        # --- Tool selection entropy ---
        tool_calls = [entry.get("tool", "") for entry in tool_log if entry.get("tool")]
        correct_tools = set(state.get("correct_tools", []))
        total_tools = state.get("total_tools", 50)
        entropy = tool_selection_entropy(tool_calls, correct_tools, total_tools)

        # --- Loop detection ---
        trajectory = Trajectory()
        for entry in tool_log:
            trajectory.add("tool_call", entry.get("tool", "unknown"), tool=entry.get("tool", ""))
        penalty = loop_penalty(trajectory)

        # --- Recovery scoring ---
        recovery = chaos_recovery_score(tool_log)

        # --- Efficiency ---
        runtime_eff = ratio_with_budget(duration_seconds, prepared.spec.budget.max_runtime_seconds) or 0.0
        tool_eff = ratio_with_budget(len(tool_log), prepared.spec.budget.max_tool_calls)
        efficiency = runtime_eff if tool_eff is None else (runtime_eff + tool_eff) / 2.0

        # --- Calibration ---
        calibration = calibration_score(agent_result.get("confidence"), success)

        scores = {
            "success": success,
            "safety": 1.0,  # MCP tasks don't have safety violations (yet)
            "recovery": recovery,
            "efficiency": efficiency,
            "calibration": calibration,
        }
        overall = weighted_score(scores, suite_weights)
        overall = max(0.0, overall + penalty)  # Apply loop penalty

        notes: list[str] = []
        if exit_code != 0:
            notes.append(f"Agent command exited with code {exit_code}.")
        if entropy < 0.5:
            notes.append(f"Tool selection entropy is low ({entropy:.2f}): agent may be guessing.")
        if penalty < 0:
            notes.append(f"Loop penalty applied: {penalty:.2f}")
        if success == 0.0:
            notes.append("MCP task objective was not completed.")

        return Evaluation(
            scores=scores,
            overall=round(overall, 4),
            passed=success >= 0.99 and penalty == 0.0,
            notes=notes,
            details={
                "state": state,
                "tool_log": tool_log,
                "tool_selection_entropy": entropy,
                "loop_penalty": penalty,
                "chaos_recovery": recovery,
                "agent_result": agent_result,
            },
        )

    # ---- Scenario setup helpers ----

    def _setup_file_organise(self, workspace: Path, internal: Path, fs: FilesystemServer, seed: int) -> dict:
        rng = random.Random(seed)
        files_to_organise = {}
        categories = {"reports": [], "configs": [], "logs": []}
        for i in range(rng.randint(5, 10)):
            category = rng.choice(list(categories.keys()))
            name = f"file_{i}.{rng.choice(['txt', 'json', 'yaml', 'md'])}"
            content = f"Content of {name} — category: {category}\n"
            files_to_organise[name] = {"category": category, "content": content}
            categories[category].append(name)

        # Write files flat in workspace
        for name, info in files_to_organise.items():
            (workspace / name).write_text(info["content"], encoding="utf-8")

        (workspace / "organise_rules.md").write_text(
            "# File Organisation Rules\n\n"
            "Move each file into the directory matching its category:\n"
            "- Files containing 'reports' → `reports/`\n"
            "- Files containing 'configs' → `configs/`\n"
            "- Files containing 'logs' → `logs/`\n",
            encoding="utf-8",
        )
        return {"categories": {k: sorted(v) for k, v in categories.items()}}

    def _setup_issue_triage(self, workspace: Path, internal: Path, gh: GitHubServer, seed: int) -> dict:
        rng = random.Random(seed)
        labels_to_apply = {}
        for issue in gh._issues:
            label = rng.choice(["bug", "feature", "question", "wontfix"])
            labels_to_apply[issue["id"]] = label

        write_json(workspace / "triage_rules.json", {
            "rules": [
                {"pattern": "bug", "label": "bug", "action": "label"},
                {"pattern": "feature", "label": "feature", "action": "label"},
                {"pattern": "question", "label": "question", "action": "label"},
                {"pattern": "wontfix", "label": "wontfix", "action": "close"},
            ],
            "issues_to_triage": labels_to_apply,
        })
        return {"labels": labels_to_apply}

    def _setup_incident_notify(self, workspace: Path, internal: Path, gh: GitHubServer, sl: SlackServer, seed: int) -> dict:
        rng = random.Random(seed)
        incident_title = f"Production incident #{rng.randint(1000, 9999)}"
        channel = rng.choice(["incidents", "engineering"])
        (workspace / "incident_details.md").write_text(
            f"# Incident\n\n**Title**: {incident_title}\n\n"
            f"**Severity**: P1\n**Channel**: #{channel}\n\n"
            "Create a GitHub issue, post to the Slack channel, and pin the message.\n",
            encoding="utf-8",
        )
        return {"incident_title": incident_title, "channel": channel}

    # ---- Scoring helpers ----

    def _score_file_organise(self, state: dict) -> float:
        moved = int(state.get("files_moved", 0))
        if moved >= 2:
            return 1.0
        if moved == 1:
            return 0.5
        return 0.0

    def _score_issue_triage(self, state: dict) -> float:
        labels = int(state.get("labels_applied", 0))
        closed = int(state.get("issues_closed", 0))
        if labels >= 1 and closed >= 1:
            return 1.0
        if labels >= 1 or closed >= 1:
            return 0.5
        return 0.0

    def _score_incident_notify(self, state: dict) -> float:
        checks = [
            bool(state.get("issue_created")),
            bool(state.get("slack_notified")),
            bool(state.get("message_pinned")),
        ]
        return round(sum(1.0 for item in checks if item) / len(checks), 4)


def _read_json_safe(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return read_json(path)
    except Exception:
        return default


def _mcp_server_script() -> str:
    """Generate the MCP server script that gets dropped into the agent workspace."""
    return '''"""MCP Tool Server launched by the agent under test.

Usage:
    python mcp_server.py              # stdio mode (default)
    python mcp_server.py --http PORT  # http mode

Speaks JSON-RPC 2.0 over newline-delimited JSON on stdin/stdout.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INTERNAL = ROOT / ".agentbench_internal"
STATE_PATH = INTERNAL / "state.json"
LOG_PATH = INTERNAL / "tool_log.json"
MANIFEST_PATH = ROOT / "mcp_manifest.json"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def log_call(tool, status, details=None):
    entries = read_json(LOG_PATH) if LOG_PATH.exists() else []
    entries.append({"tool": tool, "status": status, "details": details or {}})
    write_json(LOG_PATH, entries)


def handle_message(raw_msg):
    """Process one JSON-RPC message and return a response dict."""
    msg_id = raw_msg.get("id")
    method = raw_msg.get("method")
    params = raw_msg.get("params", {})

    if method == "tools/list":
        manifest = read_json(MANIFEST_PATH)
        return {"jsonrpc": "2.0", "id": msg_id, "result": manifest}

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # Load state
        state = read_json(STATE_PATH) if STATE_PATH.exists() else {}

        # Log the call
        log_call(tool_name, "ok", {"arguments": arguments})

        scenario = state.get("scenario")
        if scenario == "file_organise":
            if tool_name in ("fs_move_file", "fs_copy_file"):
                state["files_moved"] = int(state.get("files_moved", 0)) + 1
            state["completed"] = state.get("files_moved", 0) >= 2
        elif scenario == "issue_triage":
            if tool_name == "gh_add_label":
                state["labels_applied"] = int(state.get("labels_applied", 0)) + 1
            if tool_name == "gh_close_issue":
                state["issues_closed"] = int(state.get("issues_closed", 0)) + 1
            state["completed"] = state.get("labels_applied", 0) >= 1 and state.get("issues_closed", 0) >= 1
        elif scenario == "incident_notify":
            if tool_name == "gh_create_issue":
                state["issue_created"] = True
            if tool_name == "slack_send_message":
                state["slack_notified"] = True
            if tool_name == "slack_pin_message":
                state["message_pinned"] = True
            state["completed"] = bool(state.get("issue_created")) and bool(state.get("slack_notified")) and bool(state.get("message_pinned"))
        write_json(STATE_PATH, state)

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": {
                    "tool": tool_name,
                    "status": "ok",
                    "message": f"Tool {tool_name} executed successfully.",
                    "data": arguments,
                }
            },
        }

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def main():
    parser = argparse.ArgumentParser(description="MCP Tool Server")
    parser.add_argument("--http", type=int, default=None, help="Run in HTTP mode on this port")
    args = parser.parse_args()

    if args.http:
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path == "/mcp/tools":
                    manifest = read_json(MANIFEST_PATH)
                    body = json.dumps(manifest).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_error(404)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = json.loads(self.rfile.read(length).decode())
                resp = handle_message(raw)
                body = json.dumps(resp).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

        server = HTTPServer(("127.0.0.1", args.http), Handler)
        print(f"MCP server running on http://127.0.0.1:{args.http}", file=sys.stderr)
        server.serve_forever()
    else:
        # Stdio mode
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
                print(json.dumps(resp), flush=True)
                continue
            resp = handle_message(msg)
            print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
'''
