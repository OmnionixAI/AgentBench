# Omnionix AgentBench

Omnionix AgentBench is a production-oriented benchmark harness for AI agents. It evaluates code repair, data workflows, tool orchestration, MCP tool use, long-session memory drift, resumed-session reliability, and public reproducibility instead of relying on one-shot answer-only prompts.

## What `0.2.9` adds

- First-class `Agentic Reliability` tasks for persistent memory, state drift, and resumed handoffs.
- First-class `MCP` tasks in the default release suite.
- A public leaderboard pipeline with validated submissions, explicit agent identity, reproducibility hashes, and track breakdowns.
- Dynamic leaderboard site generation plus live serving with automatic refresh.
- Family- and tag-level track slices so agents can be compared on `mcp`, `reliability`, `long-session`, `workflow`, `coding`, and `data`.

## Quick Start

Run your agent:

```bash
agentbench run --agent-exec "your-agent-cli"
```

Run a long-session reliability episode:

```bash
agentbench run --task reliability.memory_refresh --seed 11 --agent-exec "your-agent-cli"
```

Run an MCP episode:

```bash
agentbench run --task mcp.file_organise --seed 11 --agent-exec "your-agent-cli"
```

List tasks:

```bash
agentbench list
```

## Integration Paths

- `CLI`: `agentbench run --agent-exec "my-agent-cli"`
- `Docker`: `agentbench run --agent-docker-image my-agent:latest`
- `Python`: `agentbench run --agent-python adapters/my_agent.py`
- `Custom`: `agentbench run --agent-command "my-agent --task {task_file} ..."`

AgentBench standardizes the invocation contract with `--task`, `--workspace`, `--result`, and `--prompt`.

## Benchmark Scope

### `repo_patch`

- `repo.timezone_window`
- `repo.rate_limit_boundary`

### `data_pipeline`

- `data.margin_hotspots`
- `data.inventory_rebalance`

### `tool_workflow`

- `workflow.support_refund`
- `workflow.incident_rollback`

### `mcp_tool_use`

- `mcp.file_organise`
- `mcp.issue_triage`
- `mcp.incident_notify`

### `agentic_reliability`

- `reliability.memory_refresh`
- `reliability.resume_handoff`

## Scoring

Default weighted dimensions in `v0.2.9`:

- `success`: 0.42
- `safety`: 0.12
- `recovery`: 0.12
- `efficiency`: 0.09
- `calibration`: 0.05
- `reliability`: 0.20

Additional report tracks include:

- `by_family`
- `by_tag`
- `consistency`
- `cost_efficiency`
- `tool-selection entropy`
- `loop penalties`

## Public Leaderboard

AgentBench now supports attributable, reproducible public submissions.

### 1. Submit a run

```bash
agentbench submit ^
  --summary runs/latest/summary.json ^
  --agent-name "Omnionix Reference Agent" ^
  --agent-version "1.4.2" ^
  --organization "Omnionix" ^
  --creator "Josh Verma" ^
  --framework "custom-cli" ^
  --model "gpt-5.2" ^
  --runtime "python" ^
  --integration "agent-exec" ^
  --website "https://example.com" ^
  --source-url "https://github.com/example/repo"
```

Every submission stores:

- agent name and version
- organization and creator
- framework, model, runtime, integration mode
- suite fingerprint
- reproducibility hash
- family and tag track scores

### 2. Build the leaderboard

```bash
agentbench build-leaderboard
```

This writes:

- `leaderboard/site/leaderboard.json`
- `leaderboard/site/index.html`

### 3. Serve it dynamically

```bash
agentbench serve-leaderboard
```

The site auto-refreshes and shows exactly which agent you are looking at: name, version, organization, creator, framework, model, runtime, links, verification status, and reproducibility hash.

## Why this helps standardization

- Public submissions reduce one-off screenshot claims.
- Explicit agent identity prevents anonymous leaderboard entries.
- Reproducibility hashes help separate real runs from unverifiable marketing.
- Reliability and long-session tracks stop one-shot optimization from dominating the ranking.
- MCP tracks make tool-using agents comparable on a standardized interface.

## Outputs

Each run creates:

- per-episode `evaluation.json`
- per-episode `trajectory.json`
- per-episode `agent_stdout.txt`
- per-episode `agent_stderr.txt`
- suite `summary.json`
- suite `summary.md`

## Debugging

Prepare a single episode:

```bash
agentbench prepare --task reliability.resume_handoff --seed 17
```

## Tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Version

This release is `0.2.9`.
