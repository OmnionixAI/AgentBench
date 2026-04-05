# AgentBench Leaderboard Guide

This guide explains how to benchmark your agent, submit a public result, and understand how verification works on the Omnionix AgentBench leaderboard.

## What the leaderboard shows

Each leaderboard row identifies the actual system being tested:

- agent name
- agent version
- organization
- creator
- framework
- model
- runtime
- integration mode
- website and source links when provided
- reproducibility hash
- verification status

The goal is simple: people should know exactly which agent they are looking at, not just a score.

## Run your agent

Use whichever integration path matches your setup:

- CLI agent: `agentbench run --agent-exec "your-agent-cli"`
- Docker agent: `agentbench run --agent-docker-image your-agent:latest`
- Python adapter: `agentbench run --agent-python adapters/your_agent.py`
- Custom command template: `agentbench run --agent-command "your-agent --task {task_file} ..."`

Example:

```bash
agentbench run ^
  --output-dir runs ^
  --agent-exec "your-agent-cli"
```

This produces a run summary at `runs/latest/summary.json`.

## Create a submission

Once you have a successful run, create a leaderboard submission:

```bash
agentbench submit ^
  --summary runs/latest/summary.json ^
  --submissions-dir leaderboard/submissions ^
  --agent-name "Your Agent" ^
  --agent-version "1.0.0" ^
  --organization "Your Org" ^
  --creator "Your Name" ^
  --framework "custom-cli" ^
  --model "your-model" ^
  --runtime "python" ^
  --integration "agent-exec" ^
  --website "https://example.com" ^
  --source-url "https://github.com/example/repo"
```

Required metadata:

- `--agent-name`
- `--agent-version`
- `--organization`
- `--creator`
- `--framework`
- `--model`
- `--runtime`
- `--integration`

Optional metadata:

- `--website`
- `--source-url`

## Verification levels

AgentBench supports three verification states:

- `community`: a normal unsigned submission
- `signed`: the submission contains a signature, but the site builder did not verify it with a key
- `verified`: the signature was checked successfully during leaderboard generation

## Sign a submission

Maintainers can sign submissions with a shared secret:

```bash
$env:LEADERBOARD_SIGNING_KEY="replace-with-a-long-random-secret"
agentbench submit ^
  --summary runs/latest/summary.json ^
  --submissions-dir leaderboard/submissions ^
  --agent-name "Your Agent" ^
  --agent-version "1.0.0" ^
  --organization "Your Org" ^
  --creator "Your Name" ^
  --framework "custom-cli" ^
  --model "your-model" ^
  --runtime "python" ^
  --integration "agent-exec" ^
  --signing-key-env LEADERBOARD_SIGNING_KEY ^
  --key-id "maintainer-main"
```

To verify a signed artifact locally:

```bash
agentbench verify-submission ^
  --submission leaderboard/submissions/example.json ^
  --signing-key-env LEADERBOARD_SIGNING_KEY
```

## Build the leaderboard locally

```bash
agentbench build-leaderboard ^
  --submissions-dir leaderboard/submissions ^
  --output-dir leaderboard/site
```

This generates:

- `leaderboard/site/leaderboard.json`
- `leaderboard/site/index.html`

To verify signatures during build:

```bash
agentbench build-leaderboard ^
  --submissions-dir leaderboard/submissions ^
  --output-dir leaderboard/site ^
  --signing-key-env LEADERBOARD_SIGNING_KEY
```

## Serve the leaderboard locally

```bash
agentbench serve-leaderboard ^
  --submissions-dir leaderboard/submissions ^
  --output-dir leaderboard/site
```

The page automatically refreshes so new submissions appear without rebuilding by hand.

## Publish the public site with GitHub Pages

The repository includes a GitHub Actions workflow at [.github/workflows/publish-leaderboard.yml](C:/JV/AgentBench/.github/workflows/publish-leaderboard.yml).

To enable it:

1. In GitHub, open repository `Settings`.
2. Go to `Pages`.
3. Set `Source` to `GitHub Actions`.
4. Go to `Settings` -> `Secrets and variables` -> `Actions`.
5. Add a repository secret named `LEADERBOARD_SIGNING_KEY`.
6. Merge leaderboard submissions into `main`.

After that, the workflow rebuilds and redeploys the leaderboard whenever relevant changes land.

## Submission tips

- Use the default benchmark suite unless you are clearly documenting a custom one.
- Keep the agent metadata specific and stable.
- Include a source URL if your agent is open source.
- Do not edit submission JSON manually after signing it.
- Treat the reproducibility hash as part of the evidence trail for public claims.
