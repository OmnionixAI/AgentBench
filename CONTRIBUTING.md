# Contributing to Omnionix AgentBench

Thanks for contributing to AgentBench. The goal of this project is to benchmark real AI agents on workflows that matter in production, so contributions should improve realism, reproducibility, reliability, or usability.

## What we welcome

- new benchmark families
- stronger evaluators and scoring logic
- better MCP scenarios
- better long-session and state-drift reliability tasks
- leaderboard and reporting improvements
- documentation and onboarding improvements
- bug fixes, tests, and performance improvements

## Contribution principles

When contributing, optimize for these qualities:

- realism: tasks should resemble actual agent work, not trivia
- reproducibility: runs should remain deterministic under a fixed seed
- attribution: leaderboard outputs should identify the agent clearly
- anti-gaming: avoid shallow patterns that agents can overfit trivially
- reliability: long-session behavior matters as much as one-shot success

## Development setup

Clone the repo, then install the package in editable mode:

```bash
python -m pip install -e .
```

Run the test suite:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

List tasks:

```bash
python -m agentbench list
```

Run a single benchmark episode:

```bash
python -m agentbench run --task reliability.memory_refresh --seed 11 --agent-python examples/agents/reference_agent.py --json
```

## Where to contribute

Core code lives in:

- `src/agentbench/`
- `tests/`
- `benchmarks/`
- `scenarios/`
- `examples/agents/`

Common areas:

- benchmark families: `src/agentbench/families/`
- runner and reporting: `src/agentbench/runner.py`
- CLI: `src/agentbench/cli.py`
- leaderboard: `src/agentbench/leaderboard.py`

## Adding benchmark tasks

When adding a task:

1. Keep it seed-driven and deterministic.
2. Make the task outcome measurable without subjective grading.
3. Prefer realistic filesystem, tool, workflow, or stateful interactions.
4. Include budgets, constraints, and failure modes when relevant.
5. Add or update tests.

Good task additions usually improve at least one of:

- coding realism
- tool-use realism
- MCP coverage
- long-session reliability
- recovery behavior
- evaluation robustness

## Adding leaderboard features

Leaderboard contributions should preserve trust:

- do not reduce agent identity fields
- do not weaken submission validation
- do not bypass verification semantics
- keep public artifacts understandable to third parties

If you change submission format or verification behavior, update:

- [README.md](C:/JV/AgentBench/README.md)
- [LEADERBOARD.md](C:/JV/AgentBench/LEADERBOARD.md)
- relevant tests in [test_benchmark.py](C:/JV/AgentBench/tests/test_benchmark.py)

## Code style

- prefer simple standard-library solutions where possible
- keep public CLI behavior explicit and documented
- avoid unnecessary dependencies
- use ASCII unless a file already requires something else
- add brief comments only when the logic is not self-evident

## Pull request checklist

Before opening a PR:

1. Run the tests.
2. Update docs if behavior changed.
3. Add tests for new CLI paths, scoring logic, or file formats.
4. Make sure your change improves benchmark quality, not just surface area.
5. Verify that you did not break reproducibility or leaderboard trust.

## Reporting issues

If you are opening an issue, include:

- what you tried
- expected behavior
- actual behavior
- task id and seed when relevant
- environment details if the problem is integration-specific

## Community standard

Be constructive, specific, and evidence-driven. AgentBench aims to become a serious standard, so contributions should help make the benchmark harder to game and easier to trust.
