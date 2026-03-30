# Omnionix AgentBench

Omnionix AgentBench is a Python benchmark package and CLI for evaluating AI agents on dynamic, seeded tasks instead of static answer-only prompts.

It is designed to close several gaps in the benchmarks most teams still lean on:

- [SWE-bench](https://www.swebench.com/) is strong for software repair, but narrow in domain.
- [AgentBench](https://github.com/THUDM/AgentBench), [WebArena](https://github.com/web-arena-x/webarena), and [OSWorld](https://os-world.github.io/) test action-taking, but each focuses on a subset of environments.
- [GAIA](https://huggingface.co/gaia-benchmark) and [tau-bench](https://github.com/sierra-research/tau-bench) are useful for assistants and tool workflows, but they still leave room for better cross-domain reproducibility, budget tracking, and consistency scoring.

This project pushes on those gaps by combining:

- Dynamic seeded task generation to reduce contamination and memorization risk.
- Cross-domain episodes covering code repair, data workflows, and tool orchestration.
- Weighted scoring across `success`, `safety`, `recovery`, `efficiency`, and `calibration`.
- Budget-aware evaluation, including runtime, file-change, and tool-call limits.
- Run artifacts that produce both JSON and Markdown scorecards.
- Multi-run consistency metrics so agents are judged on reliability, not just one lucky pass.

## Install

```bash
python -m pip install -e .
```

## CLI

List tasks:

```bash
agentbench list
```

Run the core suite against the bundled reference agent:

```bash
agentbench run ^
  --agent-exec "python examples/agents/reference_agent.py"
```

Run only one task with a specific seed:

```bash
agentbench run ^
  --task workflow.support_refund ^
  --seed 11 ^
  --agent-exec "python examples/agents/reference_agent.py"
```

Pretty-print a generated report:

```bash
agentbench report --summary runs/latest/summary.json
```

Prepare one episode so you can inspect the workspace or point your own agent at it manually:

```bash
agentbench prepare ^
  --task workflow.support_refund ^
  --seed 11
```

Scaffold a Python adapter for your own agent:

```bash
agentbench init-adapter --output adapters/my_agent.py
```

## Testing your own agent

There are now four straightforward integration paths.

### 1. Existing CLI agent, no wrapper needed

If your agent already runs from the command line, this is the easiest option:

```bash
agentbench run ^
  --agent-exec "my-agent-cli"
```

AgentBench automatically appends:

- `--task <path>`
- `--workspace <path>`
- `--result <path>`
- `--prompt <path>`

That means tools like `my-agent-cli`, `uv run my_agent`, `node my-agent.js`, or `npx @org/agent` can be benchmarked directly as long as they accept those flags.

### 2. Dockerized agent

If your agent already runs in a container, AgentBench can test it directly:

```bash
agentbench run ^
  --agent-docker-image my-agent:latest
```

AgentBench mounts the generated episode into the container and passes:

- `--task /agentbench_run/task.json`
- `--workspace /agentbench_run/workspace`
- `--result /agentbench_run/workspace/agent_result.json`
- `--prompt /agentbench_run/prompt.md`

If your image needs a specific command or environment variables:

```bash
agentbench run ^
  --agent-docker-image python:3.13-slim ^
  --agent-docker-command "python /agentbench_host_repo/examples/agents/reference_agent.py" ^
  --agent-docker-args "-e PYTHONPATH=/agentbench_host_repo/src"
```

AgentBench also mounts the current repo read-only at `/agentbench_host_repo`, which is useful when your image needs access to local source code or configs at runtime.

### 3. Python adapter mode

If your agent can be wrapped in Python, generate a scaffold and plug your runtime into it:

```bash
agentbench init-adapter --output adapters/my_agent.py
agentbench run --agent-python adapters/my_agent.py
```

Your adapter receives:

- `--task`: path to the public task manifest
- `--workspace`: the directory your agent should operate inside
- `--result`: where to write `agent_result.json`
- `--prompt`: the generated task prompt

The helper API in `agentbench.adapters` gives you:

- `load_context(...)` to read the task contract
- `write_result(...)` to emit a valid final result file

### 4. Full custom command template

If you need total control over invocation, you can still use the raw command-template mode:

```bash
agentbench run ^
  --agent-command "my-agent-cli --task {task_file} --workspace {workspace} --result {result_file} --prompt {prompt_file}"
```

### Manual debugging flow

If you are integrating a new agent and want to inspect a task first:

```bash
agentbench prepare --task repo.timezone_window --seed 11
```

That materializes the workspace, prompt, task file, and expected result path so you can debug your agent outside the full benchmark loop.

## Benchmark dimensions

- `success`: Did the agent achieve the objective?
- `safety`: Did it avoid forbidden edits, PII leaks, or policy violations?
- `recovery`: Did it recover from injected transient failures when the task required it?
- `efficiency`: Did it stay within runtime and action budgets?
- `calibration`: Did confidence match actual performance?

The default weighted score is:

- `success`: `0.55`
- `safety`: `0.15`
- `recovery`: `0.15`
- `efficiency`: `0.10`
- `calibration`: `0.05`

When a dimension does not apply to a task, AgentBench renormalizes the weights instead of silently distorting totals.

## Core suite

The starter suite includes six tasks with default seeded episodes:

- `repo.timezone_window`
- `repo.rate_limit_boundary`
- `data.margin_hotspots`
- `data.inventory_rebalance`
- `workflow.support_refund`
- `workflow.incident_rollback`

These cover:

- Code repair without letting agents game the benchmark by editing tests.
- Data analysis with output-format checks and PII penalties.
- Tool workflows with transient failure injection, policy compliance, and side-effect validation.

## Outputs

Each run creates:

- Per-episode `evaluation.json`
- Per-episode `agent_stdout.txt` and `agent_stderr.txt`
- Suite `summary.json`
- Suite `summary.md`

The summary includes aggregate metrics and a consistency score across runs.

## Tests

Run the smoke tests with:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Notes

This project is intentionally honest about what "better than industry standard" means: no benchmark is universally best for every agent. AgentBench is built to be stronger than common static or single-domain standards on contamination resistance, action-based evaluation, budget awareness, and repeatability.
