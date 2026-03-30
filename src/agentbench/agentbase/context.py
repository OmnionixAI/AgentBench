"""Execution context and runner framework for AgentBase."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Type


class ExecutionContext:
    """Provides tools and context for an executing agent.

    This wraps the arguments passed by AgentBench (workspace, prompt, etc.)
    and standardizes result submission and logging.
    """

    def __init__(self, workspace: Path, prompt_path: Path, result_path: Path):
        self.workspace = workspace
        self.prompt_path = prompt_path
        self.result_path = result_path

    @property
    def prompt(self) -> str:
        """Returns the content of the prompt specific to this task."""
        return self.prompt_path.read_text(encoding="utf-8")

    def submit(self, summary: str, confidence: float = 0.5, artifacts: dict[str, Any] | None = None) -> None:
        """Submit the final result of the agent execution back to the benchmark.

        Writes the structured result to `result_path` as expected by AgentBench.
        """
        payload = {
            "summary": summary,
            "confidence": confidence,
            "artifacts": artifacts or {},
        }
        self.result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def log_thought(self, text: str) -> None:
        """Emit a structured thought log to stdout for AgentBench's Trajectory tracking."""
        print(f"[THOUGHT] {text}", flush=True)

    def log_tool_call(self, tool_name: str) -> None:
        """Emit a structured tool call log to stdout for AgentBench's Trajectory tracking."""
        print(f"[TOOL_CALL] {tool_name}", flush=True)

    def log_observation(self, text: str) -> None:
        """Emit a structured observation log to stdout for AgentBench's Trajectory tracking."""
        print(f"[OBSERVATION] {text}", flush=True)

    def log_error(self, text: str) -> None:
        """Emit a structured error log to stdout for AgentBench's Trajectory tracking."""
        print(f"[ERROR] {text}", flush=True)


def run_agent(agent_cls: Type["BaseAgent"]) -> None:  # type: ignore # dynamic typing
    """Parse AgentBench CLI flags and orchestrate an agent subclass.

    This intercepts `--workspace`, `--prompt`, and `--result` passed by the harness.
    """
    parser = argparse.ArgumentParser(description="AgentBase runner")
    parser.add_argument("--workspace", type=Path, required=True, help="Path to the task workspace")
    parser.add_argument("--prompt", type=Path, required=True, help="Path to the initial prompt file")
    parser.add_argument("--result", type=Path, required=True, help="Path to write the output JSON result")
    # AgentBench passes --task-file too, which we can parse and ignore if unneeded
    parser.add_argument("--task-file", type=Path, help="Task specification file")

    args, unknown = parser.parse_known_args()

    context = ExecutionContext(
        workspace=args.workspace,
        prompt_path=args.prompt,
        result_path=args.result,
    )

    agent = agent_cls()
    
    try:
        agent.execute(context)
    except Exception as e:
        context.log_error(f"Agent execution crashed: {e}")
        sys.exit(1)
