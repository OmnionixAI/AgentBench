# Omnionix AgentBench

[![Leaderboard](https://img.shields.io/badge/Leaderboard-Live%20Rankings-0f766e?style=for-the-badge)](https://omnionixai.github.io/AgentBench/)

Omnionix AgentBench is a production-oriented benchmark harness for AI agents. It evaluates code repair, data workflows, tool orchestration, MCP tool use, long-session memory drift, resumed-session reliability, and public reproducibility instead of relying on one-shot answer-only prompts.

Helpful docs:

- [Live Leaderboard](https://omnionixai.github.io/AgentBench/)
- [Leaderboard Guide](C:/JV/AgentBench/LEADERBOARD.md)
- [Contributing Guide](C:/JV/AgentBench/CONTRIBUTING.md)

## What `0.2.9` adds

- First-class `Agentic Reliability` tasks for persistent memory, state drift, and resumed handoffs.
- First-class `MCP` tasks in the default release suite.
- A public leaderboard pipeline with validated submissions, explicit agent identity, reproducibility hashes, signed attestations, and track breakdowns.
- Dynamic leaderboard site generation plus live serving with automatic refresh.
- A GitHub Actions publishing path so the public leaderboard rebuilds automatically when new submissions are merged.
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

Compare two runs:

```bash
agentbench compare --baseline runs/20260330-100000 --current runs/latest
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
  --creator "OmnionixAI" ^
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

### Signed submissions

Maintainers can sign a submission so the leaderboard can distinguish community entries from verified attestations:

```bash
$env:LEADERBOARD_SIGNING_KEY="replace-with-your-secret"
agentbench submit ^
  --summary runs/latest/summary.json ^
  --submissions-dir leaderboard/submissions ^
  --agent-name "Omnionix Reference Agent" ^
  --agent-version "0.2.9" ^
  --organization "Omnionix" ^
  --creator "OmnionixAI" ^
  --framework "custom-cli" ^
  --model "gpt-5.2" ^
  --runtime "python" ^
  --integration "agent-exec" ^
  --signing-key-env LEADERBOARD_SIGNING_KEY ^
  --key-id "omnionix-main"
```

You can verify a signed artifact locally:

```bash
agentbench verify-submission ^
  --submission leaderboard/submissions/example.json ^
  --signing-key-env LEADERBOARD_SIGNING_KEY
```

Verification statuses shown on the leaderboard:

- `community`: unsigned community submission
- `signed`: signed artifact without a verification key loaded by the site builder
- `verified`: signature checked successfully during leaderboard generation

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

### 4. Publish it automatically

The repo includes a GitHub Actions workflow that rebuilds the site on every push affecting `leaderboard/submissions/` or the leaderboard codepath. To enable verified publishing:

1. Turn on GitHub Pages for the repository and use GitHub Actions as the source.
2. Maintainers should add a repository secret named `LEADERBOARD_SIGNING_KEY` for GitHub Actions verification.
3. Commit submissions into `leaderboard/submissions/`.

Once merged to `main`, the workflow regenerates `leaderboard/site/` and deploys it to Pages.

### 5. Validate submissions in PRs

The repo also includes a `validate-submissions` workflow so incoming leaderboard entries are checked before merge. The seamless public path is:

1. Run the benchmark.
2. Generate a submission with `agentbench submit`.
3. Commit the JSON into `leaderboard/submissions/`.
4. Open a PR.
5. Let `validate-submissions` pass.
6. Maintainers optionally sign or attest trusted submissions.
7. Merge to `main`.
8. Let `publish-leaderboard` deploy the update.

Outside contributors do not need the repository signing secret. Unsigned submissions can still be accepted and appear as `community`, while maintainer-attested submissions can appear as `verified`.

## Why this helps standardization

- Public submissions reduce one-off screenshot claims.
- Explicit agent identity prevents anonymous leaderboard entries.
- Reproducibility hashes help separate real runs from unverifiable marketing.
- Signed attestations make it harder to spoof a leaderboard row without maintainer participation.
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

## Cross-Run Comparison

AgentBench can compare two completed runs and detect regressions across aggregate scores, consistency, and FinOps metrics.

Examples:

```bash
agentbench compare --baseline runs/20260330-100000 --current runs/latest
agentbench compare --current runs/latest --output-dir runs --window 1 --threshold 0.05
agentbench compare --baseline runs/20260330-100000 --current runs/latest --json
```

Notes:

- `--window 1` compares against the previous completed timestamped run
- the command exits with code `1` when regressions are detected, which makes it CI-friendly
- `--json` emits machine-readable deltas for automation

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
