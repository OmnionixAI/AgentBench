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
  --agent-command "python examples/agents/reference_agent.py --task {task_file} --workspace {workspace} --result {result_file}"
```

Run only one task with a specific seed:

```bash
agentbench run ^
  --task workflow.support_refund ^
  --seed 11 ^
  --agent-command "python examples/agents/reference_agent.py --task {task_file} --workspace {workspace} --result {result_file}"
```

Pretty-print a generated report:

```bash
agentbench report --summary runs/latest/summary.json
```

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
