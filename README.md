# Omnionix AgentBench

Omnionix AgentBench is a production-oriented benchmark harness for AI agents. It evaluates real agent behavior across code repair, data workflows, tool orchestration, MCP tool use, and long-session reliability instead of relying on one-shot answer-only prompts.

## Why this version is stronger

- Dynamic seeded tasks reduce contamination and memorization risk.
- MCP tasks evaluate tool selection under large manifests and decoy tools.
- Agentic reliability tasks measure long-session state drift, checkpoint resumption, and persistent memory quality.
- Weighted scoring combines `success`, `safety`, `recovery`, `efficiency`, `calibration`, and `reliability`.
- Reports include JSON and Markdown summaries, trajectory logs, and optional token-cost metrics.

## Install

```bash
python -m pip install -e .
```

## Quick Start

Run your CLI agent directly:

```bash
agentbench run --agent-exec "your-agent-cli"
```

Run a containerized agent:

```bash
agentbench run --agent-docker-image your-agent:latest
```

Run a single reliability episode:

```bash
agentbench run --task reliability.memory_refresh --seed 11 --agent-exec "your-agent-cli"
```

List tasks:

```bash
agentbench list
```

Render the latest report:

```bash
agentbench report --summary runs/latest/summary.json
```

## Integration Paths

### 1. CLI agent

```bash
agentbench run --agent-exec "my-agent-cli"
```

AgentBench appends `--task`, `--workspace`, `--result`, and `--prompt`.

### 2. Docker agent

```bash
agentbench run --agent-docker-image my-agent:latest
```

AgentBench mounts the episode at `/agentbench_run` and passes the same standard flags.

### 3. Python adapter

```bash
agentbench init-adapter --output adapters/my_agent.py
agentbench run --agent-python adapters/my_agent.py
```

### 4. Custom command template

```bash
agentbench run --agent-command "my-agent --task {task_file} --workspace {workspace} --result {result_file} --prompt {prompt_file}"
```

## Core Task Families

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
- `mcp.incident_notify`

These tasks expose an MCP manifest with many tools and decoys, then score whether the agent chooses the right server actions instead of exploring randomly.

### `agentic_reliability`

- `reliability.memory_refresh`
- `reliability.resume_handoff`

These tasks stress the exact failure mode people complain about in production: the agent succeeds early, then loses the thread after many turns, stale corrections, or a resumed session.

## Scoring

Default weighted dimensions in `v0.2.7`:

- `success`: 0.42
- `safety`: 0.12
- `recovery`: 0.12
- `efficiency`: 0.09
- `calibration`: 0.05
- `reliability`: 0.20

The weighted score renormalizes automatically when a dimension does not apply to a task.

### Reliability

Reliability tasks score:

- retention of current canonical facts
- resistance to stale fact drift
- consistency between final answer and memory snapshot
- resumed-session correctness after stale checkpoints

### MCP

MCP tasks report:

- objective completion
- tool-selection entropy
- loop penalties
- chaos recovery when failures are injected

## Outputs

Each run creates:

- per-episode `evaluation.json`
- per-episode `trajectory.json`
- per-episode `agent_stdout.txt`
- per-episode `agent_stderr.txt`
- suite `summary.json`
- suite `summary.md`

If your agent reports token usage, AgentBench also computes optional cost metrics.

## Manual Debugging

Prepare a single episode without running an agent:

```bash
agentbench prepare --task reliability.resume_handoff --seed 17
```

That materializes the workspace, prompt, task manifest, and result path so you can inspect exactly what the agent sees.

## Tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Version

This release is `0.2.7`. It adds first-class MCP evaluation, first-class long-session reliability testing, and updated default suite weights that reward production-grade consistency instead of one-shot task luck.
