from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from agentbench import __version__
from agentbench.security import sign_submission, verify_submission
from agentbench.utils import ensure_dir, read_json, stable_hash, write_json


REQUIRED_AGENT_FIELDS = [
    "name",
    "version",
    "organization",
    "creator",
    "framework",
    "model",
    "runtime",
    "integration",
]


class SubmissionValidationError(ValueError):
    """Raised when a leaderboard submission is malformed or incomplete."""


def create_submission(summary_path: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    summary = read_json(summary_path)
    agent = metadata["agent"]
    missing = [field for field in REQUIRED_AGENT_FIELDS if not str(agent.get(field, "")).strip()]
    if missing:
        raise ValueError(f"Missing required agent metadata fields: {', '.join(missing)}")

    submission_time = metadata.get("submitted_at") or datetime.now(UTC).isoformat()
    run_provenance = {
        "agentbench_version": summary.get("agentbench_version", __version__),
        "suite_name": summary["suite"]["name"],
        "suite_version": summary["suite"]["version"],
        "suite_fingerprint": summary["suite"].get("fingerprint"),
        "episodes": summary["episodes"],
    }
    submission_id = stable_hash(
        {
            "agent": agent,
            "suite_fingerprint": run_provenance["suite_fingerprint"],
            "averages": summary.get("averages", {}),
            "consistency": summary.get("consistency"),
            "submitted_at": submission_time,
        }
    )[:16]

    submission = {
        "submission_id": submission_id,
        "submitted_at": submission_time,
        "agent": agent,
        "links": metadata.get("links", {}),
        "run": {
            "summary_path": str(summary_path),
            "run_dir": summary.get("run_dir"),
            "benchmark": run_provenance,
            "averages": summary.get("averages", {}),
            "consistency": summary.get("consistency"),
            "passed": summary.get("passed"),
            "failed": summary.get("failed"),
            "episodes": summary.get("episodes"),
            "by_family": summary.get("by_family", {}),
            "by_tag": summary.get("by_tag", {}),
            "finops": summary.get("finops", {}),
        },
        "verification": {
            "summary_hash": stable_hash(summary),
            "reproducibility_hash": stable_hash(
                {
                    "suite_fingerprint": run_provenance["suite_fingerprint"],
                    "task_results": summary.get("tasks", []),
                }
            ),
            "verified": bool(metadata.get("verified", False)),
            "verification_status": "community",
        },
        "benchmark_card": {
            "reliability": summary.get("averages", {}).get("reliability"),
            "mcp": _family_average(summary, "mcp_tool_use"),
            "workflow": _family_average(summary, "tool_workflow"),
            "coding": _family_average(summary, "repo_patch"),
            "data": _family_average(summary, "data_pipeline"),
            "long_session": _tag_average(summary, "long-session"),
            "cost_efficiency": summary.get("finops", {}).get("avg_efficiency_score"),
        },
    }
    signing = metadata.get("signing", {})
    signing_key = signing.get("secret")
    if signing_key:
        submission["verification"]["verification_status"] = "signed"
        submission = sign_submission(submission, signing_key, key_id=signing.get("key_id", "maintainer"))
    return submission


def save_submission(submission: dict[str, Any], submissions_dir: Path) -> Path:
    ensure_dir(submissions_dir)
    path = submissions_dir / f"{submission['submission_id']}.json"
    write_json(path, submission)
    return path


def validate_submission(submission: dict[str, Any], signing_secret: str | None = None) -> dict[str, Any]:
    missing = [field for field in REQUIRED_AGENT_FIELDS if not str(submission.get("agent", {}).get(field, "")).strip()]
    if missing:
        raise SubmissionValidationError(f"Missing required agent fields: {', '.join(missing)}")

    if not str(submission.get("submission_id", "")).strip():
        raise SubmissionValidationError("Missing submission_id.")

    run = submission.get("run")
    if not isinstance(run, dict):
        raise SubmissionValidationError("Missing run block.")

    benchmark = run.get("benchmark")
    if not isinstance(benchmark, dict):
        raise SubmissionValidationError("Missing run.benchmark block.")

    if not str(benchmark.get("suite_name", "")).strip():
        raise SubmissionValidationError("Missing run.benchmark.suite_name.")
    if not str(benchmark.get("suite_version", "")).strip():
        raise SubmissionValidationError("Missing run.benchmark.suite_version.")
    if not str(benchmark.get("suite_fingerprint", "")).strip():
        raise SubmissionValidationError("Missing run.benchmark.suite_fingerprint.")

    verification = submission.get("verification")
    if not isinstance(verification, dict):
        raise SubmissionValidationError("Missing verification block.")
    if not str(verification.get("summary_hash", "")).strip():
        raise SubmissionValidationError("Missing verification.summary_hash.")
    if not str(verification.get("reproducibility_hash", "")).strip():
        raise SubmissionValidationError("Missing verification.reproducibility_hash.")

    if "averages" not in run or not isinstance(run.get("averages"), dict):
        raise SubmissionValidationError("Missing run.averages block.")

    verified_signature, verification_reason = verify_submission(submission, signing_secret)
    verification_status = "verified" if verified_signature else verification.get("verification_status", "community")
    if verification_status not in {"community", "signed", "verified"}:
        raise SubmissionValidationError(f"Unsupported verification status: {verification_status}")

    return {
        "submission_id": submission["submission_id"],
        "agent_name": submission["agent"]["name"],
        "verified": verified_signature or bool(verification.get("verified")),
        "verification_status": verification_status,
        "verification_reason": verification_reason,
    }


def validate_submissions_dir(submissions_dir: Path, signing_secret: str | None = None) -> dict[str, Any]:
    results = []
    for path in sorted(submissions_dir.glob("*.json")) if submissions_dir.exists() else []:
        try:
            submission = read_json(path)
            details = validate_submission(submission, signing_secret=signing_secret)
            results.append({"path": str(path), "valid": True, **details})
        except Exception as exc:
            results.append({"path": str(path), "valid": False, "error": str(exc)})

    invalid = [result for result in results if not result["valid"]]
    return {
        "count": len(results),
        "valid": len(results) - len(invalid),
        "invalid": len(invalid),
        "results": results,
    }


def build_leaderboard(submissions_dir: Path, output_dir: Path, signing_secret: str | None = None) -> Path:
    ensure_dir(output_dir)
    submissions = _load_submissions(submissions_dir, strict=True)
    rows = []
    for submission in submissions:
        validate_submission(submission, signing_secret=signing_secret)
        verified_signature, verification_reason = verify_submission(submission, signing_secret)
        averages = submission["run"]["averages"]
        verification_status = "verified" if verified_signature else submission.get("verification", {}).get("verification_status", "community")
        rows.append(
            {
                "submission_id": submission["submission_id"],
                "agent_name": submission["agent"]["name"],
                "agent_version": submission["agent"]["version"],
                "organization": submission["agent"]["organization"],
                "creator": submission["agent"]["creator"],
                "framework": submission["agent"]["framework"],
                "model": submission["agent"]["model"],
                "runtime": submission["agent"]["runtime"],
                "integration": submission["agent"]["integration"],
                "website": submission.get("links", {}).get("website"),
                "source_url": submission.get("links", {}).get("source_url"),
                "overall": averages.get("overall"),
                "reliability": averages.get("reliability"),
                "success": averages.get("success"),
                "safety": averages.get("safety"),
                "recovery": averages.get("recovery"),
                "efficiency": averages.get("efficiency"),
                "calibration": averages.get("calibration"),
                "consistency": submission["run"].get("consistency"),
                "mcp": submission["benchmark_card"].get("mcp"),
                "workflow": submission["benchmark_card"].get("workflow"),
                "coding": submission["benchmark_card"].get("coding"),
                "data": submission["benchmark_card"].get("data"),
                "long_session": submission["benchmark_card"].get("long_session"),
                "cost_efficiency": submission["benchmark_card"].get("cost_efficiency"),
                "verified": verified_signature or submission["verification"]["verified"],
                "verification_status": verification_status,
                "verification_reason": verification_reason,
                "key_id": submission.get("verification", {}).get("signature", {}).get("key_id"),
                "suite_version": submission["run"]["benchmark"]["suite_version"],
                "suite_fingerprint": submission["run"]["benchmark"]["suite_fingerprint"],
                "submitted_at": submission["submitted_at"],
                "reproducibility_hash": submission["verification"]["reproducibility_hash"],
            }
        )

    rows.sort(key=lambda row: ((row["overall"] or 0.0), (row["reliability"] or 0.0), (row["consistency"] or 0.0)), reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index

    payload = {
        "leaderboard_version": "1",
        "generated_at": datetime.now(UTC).isoformat(),
        "agentbench_version": __version__,
        "submissions": rows,
    }
    json_path = output_dir / "leaderboard.json"
    write_json(json_path, payload)
    (output_dir / "index.html").write_text(_leaderboard_html(), encoding="utf-8")
    return json_path


def serve_leaderboard(submissions_dir: Path, output_dir: Path, host: str, port: int, signing_secret: str | None = None) -> None:
    build_leaderboard(submissions_dir, output_dir, signing_secret=signing_secret)
    output_dir = output_dir.resolve()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(output_dir), **kwargs)

        def do_GET(self):
            if self.path in ("/", "/index.html", "/leaderboard.json"):
                build_leaderboard(submissions_dir, output_dir, signing_secret=signing_secret)
            return super().do_GET()

    server = ThreadingHTTPServer((host, port), Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _load_submissions(submissions_dir: Path, strict: bool = False) -> list[dict[str, Any]]:
    if not submissions_dir.exists():
        return []
    submissions = []
    for path in sorted(submissions_dir.glob("*.json")):
        try:
            submissions.append(read_json(path))
        except Exception:
            if strict:
                raise
            continue
    return submissions


def read_signing_secret(env_name: str | None) -> str | None:
    if not env_name:
        return None
    return os.getenv(env_name)


def _family_average(summary: dict[str, Any], family: str) -> float | None:
    family_block = summary.get("by_family", {}).get(family)
    if not family_block:
        return None
    return family_block.get("average_overall")


def _tag_average(summary: dict[str, Any], tag: str) -> float | None:
    tag_block = summary.get("by_tag", {}).get(tag)
    if not tag_block:
        return None
    return tag_block.get("average_overall")


def _leaderboard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Omnionix AgentBench Leaderboard</title>
  <style>
    :root {
      --bg: #07111f;
      --panel: #0f1c2d;
      --panel-2: #12243a;
      --text: #ecf3ff;
      --muted: #98abc7;
      --line: #244261;
      --accent: #6ee7c8;
      --warm: #ffc86b;
      --danger: #ff8f8f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "Aptos", sans-serif;
      background: radial-gradient(circle at top, #153559 0%, var(--bg) 55%);
      color: var(--text);
    }
    .wrap { max-width: 1400px; margin: 0 auto; padding: 32px 24px 56px; }
    .hero { display: grid; gap: 14px; margin-bottom: 24px; }
    .eyebrow { color: var(--accent); text-transform: uppercase; letter-spacing: .18em; font-size: 12px; }
    h1 { margin: 0; font-size: clamp(32px, 5vw, 56px); line-height: 1.02; }
    .sub { color: var(--muted); max-width: 900px; line-height: 1.5; }
    .meta, .filters {
      display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
      background: rgba(15, 28, 45, 0.84); border: 1px solid var(--line); border-radius: 18px;
      padding: 14px 16px; backdrop-filter: blur(10px);
    }
    .status-card {
      margin-top: 14px;
      background: rgba(15, 28, 45, 0.88);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      display: grid;
      gap: 8px;
    }
    .status-title { font-size: 12px; text-transform: uppercase; letter-spacing: .12em; color: var(--muted); }
    .status-row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
    .chip { background: var(--panel-2); border: 1px solid var(--line); border-radius: 999px; padding: 8px 12px; color: var(--muted); }
    .chip.good { color: var(--accent); }
    .chip.bad { color: var(--danger); }
    .chip.warn { color: var(--warm); }
    .section { margin-top: 24px; }
    .section-head { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 10px; }
    .section-head h2 { margin: 0; font-size: 22px; }
    input, select {
      background: #091727; color: var(--text); border: 1px solid var(--line); border-radius: 10px;
      padding: 10px 12px;
    }
    table { width: 100%; border-collapse: collapse; margin-top: 18px; background: rgba(15, 28, 45, 0.88); border-radius: 18px; overflow: hidden; }
    th, td { padding: 14px 12px; border-bottom: 1px solid rgba(36, 66, 97, 0.75); text-align: left; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .08em; cursor: pointer; }
    tbody tr:hover { background: rgba(18, 36, 58, 0.9); }
    .agent { display: grid; gap: 4px; }
    .agent strong { font-size: 15px; }
    .agent span { color: var(--muted); font-size: 13px; }
    .metric { font-variant-numeric: tabular-nums; }
    .verified { color: var(--accent); }
    .unverified { color: var(--warm); }
    a { color: var(--accent); text-decoration: none; }
    @media (max-width: 980px) {
      table, thead, tbody, th, td, tr { display: block; }
      thead { display: none; }
      tr { padding: 12px; border-bottom: 1px solid var(--line); }
      td { border: 0; padding: 6px 0; }
      td::before { content: attr(data-label); color: var(--muted); display: block; font-size: 12px; text-transform: uppercase; margin-bottom: 2px; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="eyebrow">Omnionix AgentBench</div>
      <h1>Public Leaderboard</h1>
      <div class="sub">Dynamic, attributable rankings for agent systems. Every row identifies the agent, version, framework, model, runtime, reproducibility hash, and the benchmark dimensions that matter in production.</div>
    </div>
    <div class="meta">
      <div class="chip" id="generated">Loading leaderboard...</div>
      <div class="chip" id="count">0 submissions</div>
      <div class="chip" id="verified-count">0 verified</div>
      <div class="chip" id="community-count">0 community</div>
      <div class="chip">Auto-refresh: 60s</div>
    </div>
    <div class="status-card">
      <div class="status-title">Latest Regression Check</div>
      <div class="status-row">
        <div class="chip" id="ci-status">Loading CI status...</div>
        <div class="chip" id="ci-threshold">Threshold: n/a</div>
        <div class="chip" id="ci-regressions">Regressions: n/a</div>
      </div>
      <div id="ci-meta" style="color:#98abc7;font-size:13px;">Waiting for CI metadata...</div>
    </div>
    <div class="filters" style="margin-top: 14px;">
      <input id="search" placeholder="Filter by agent, org, model, framework">
      <select id="sort">
        <option value="overall">Sort: Overall</option>
        <option value="reliability">Sort: Reliability</option>
        <option value="mcp">Sort: MCP</option>
        <option value="consistency">Sort: Consistency</option>
        <option value="cost_efficiency">Sort: Cost Efficiency</option>
      </select>
    </div>
    <div class="section">
      <div class="section-head">
        <h2>Verified</h2>
        <div class="chip good" id="verified-summary">0 trusted entries</div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Rank</th><th>Agent</th><th>Overall</th><th>Reliability</th><th>MCP</th><th>Consistency</th><th>Cost</th><th>Verification</th>
          </tr>
        </thead>
        <tbody id="verified-rows"></tbody>
      </table>
    </div>
    <div class="section">
      <div class="section-head">
        <h2>Community</h2>
        <div class="chip warn" id="community-summary">0 community entries</div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Rank</th><th>Agent</th><th>Overall</th><th>Reliability</th><th>MCP</th><th>Consistency</th><th>Cost</th><th>Verification</th>
          </tr>
        </thead>
        <tbody id="community-rows"></tbody>
      </table>
    </div>
  </div>
  <script>
    const state = { rows: [], sort: "overall", search: "" };
    async function load() {
      const response = await fetch("leaderboard.json?ts=" + Date.now());
      const data = await response.json();
      state.rows = data.submissions || [];
      document.getElementById("generated").textContent = "Generated " + new Date(data.generated_at).toLocaleString();
      document.getElementById("count").textContent = `${state.rows.length} submissions`;
      const verifiedRows = state.rows.filter(row => !!row.verified);
      const communityRows = state.rows.filter(row => !row.verified);
      document.getElementById("verified-count").textContent = `${verifiedRows.length} verified`;
      document.getElementById("community-count").textContent = `${communityRows.length} community`;
      document.getElementById("verified-summary").textContent = `${verifiedRows.length} trusted entries`;
      document.getElementById("community-summary").textContent = `${communityRows.length} community entries`;
      render();
      loadCiStatus();
    }
    async function loadCiStatus() {
      const chip = document.getElementById("ci-status");
      const threshold = document.getElementById("ci-threshold");
      const regressions = document.getElementById("ci-regressions");
      const meta = document.getElementById("ci-meta");
      try {
        const response = await fetch("ci_status.json?ts=" + Date.now());
        if (!response.ok) {
          throw new Error("missing");
        }
        const data = await response.json();
        chip.className = "chip " + (data.status_class || "");
        chip.textContent = data.status_label || "CI status unavailable";
        threshold.textContent = `Threshold: ${data.regression_threshold ?? "n/a"}`;
        regressions.textContent = `Regressions: ${data.regression_count ?? "n/a"}`;
        let detail = data.summary || "No CI summary available.";
        if (data.run_url) {
          detail += ` `;
          detail += `<a href="${data.run_url}" target="_blank" rel="noreferrer">Open workflow run</a>`;
        }
        meta.innerHTML = detail;
      } catch (error) {
        chip.className = "chip warn";
        chip.textContent = "CI status unavailable";
        threshold.textContent = "Threshold: n/a";
        regressions.textContent = "Regressions: n/a";
        meta.textContent = "The leaderboard was published without CI status metadata.";
      }
    }
    function metric(value) {
      return value === null || value === undefined ? "n/a" : Number(value).toFixed(4);
    }
    function filteredRows() {
      let rows = [...state.rows];
      if (state.search) {
        const q = state.search.toLowerCase();
        rows = rows.filter(row => [row.agent_name, row.organization, row.model, row.framework].join(" ").toLowerCase().includes(q));
      }
      rows.sort((a, b) => (b[state.sort] ?? -1) - (a[state.sort] ?? -1));
      return rows;
    }
    function rowHtml(row, index) {
      return `
        <td data-label="Rank" class="metric">${index + 1}</td>
        <td data-label="Agent">
          <div class="agent">
            <strong>${row.agent_name} <span style="color:#98abc7;">v${row.agent_version}</span></strong>
            <span>${row.organization} | ${row.creator}</span>
            <span>${row.framework} | ${row.model} | ${row.runtime}</span>
            <span>${row.integration}${row.website ? ` | <a href="${row.website}" target="_blank" rel="noreferrer">website</a>` : ""}${row.source_url ? ` | <a href="${row.source_url}" target="_blank" rel="noreferrer">source</a>` : ""}</span>
          </div>
        </td>
        <td data-label="Overall" class="metric">${metric(row.overall)}</td>
        <td data-label="Reliability" class="metric">${metric(row.reliability)}</td>
        <td data-label="MCP" class="metric">${metric(row.mcp)}</td>
        <td data-label="Consistency" class="metric">${metric(row.consistency)}</td>
        <td data-label="Cost Efficiency" class="metric">${metric(row.cost_efficiency)}</td>
        <td data-label="Verification">
          <div class="${row.verified ? "verified" : "unverified"}">${row.verification_status || (row.verified ? "verified" : "community")}</div>
          <div style="color:#98abc7;font-size:12px;">${row.key_id ? `key ${row.key_id}` : row.verification_reason}</div>
          <div style="color:#98abc7;font-size:12px;">${row.reproducibility_hash.slice(0, 12)}</div>
        </td>
      `;
    }
    function renderBucket(targetId, rows) {
      const tbody = document.getElementById(targetId);
      tbody.innerHTML = "";
      rows.forEach((row, index) => {
        const tr = document.createElement("tr");
        tr.innerHTML = rowHtml(row, index);
        tbody.appendChild(tr);
      });
    }
    function render() {
      const rows = filteredRows();
      renderBucket("verified-rows", rows.filter(row => !!row.verified));
      renderBucket("community-rows", rows.filter(row => !row.verified));
    }
    document.getElementById("search").addEventListener("input", event => { state.search = event.target.value.trim(); render(); });
    document.getElementById("sort").addEventListener("change", event => { state.sort = event.target.value; render(); });
    load();
    setInterval(load, 60000);
  </script>
</body>
</html>
"""
