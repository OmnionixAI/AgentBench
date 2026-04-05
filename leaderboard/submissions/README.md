# Leaderboard Submissions

This folder contains public leaderboard submissions for Omnionix AgentBench.

## How it works

1. Run AgentBench against your agent.
2. Generate a submission JSON with `agentbench submit`.
3. Add the generated file to this folder.
4. Open a pull request.
5. The `validate-submissions` workflow checks the submission format.
6. After merge to `main`, the `publish-leaderboard` workflow rebuilds the public leaderboard.

## Create a submission

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
  --integration "agent-exec"
```

## Optional signing

Maintainers can sign submissions before they are merged:

```bash
$env:LEADERBOARD_SIGNING_KEY="replace-with-your-secret"
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

## Validation

Validate locally before opening a PR:

```bash
agentbench validate-submissions --submissions-dir leaderboard/submissions --json
```

## Rules

- Do not edit signed submission JSON manually.
- Keep one submission per generated JSON file.
- Use stable, recognizable agent identity fields.
- Include `--website` and `--source-url` when available.
