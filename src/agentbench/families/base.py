from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from agentbench.models import Evaluation, PreparedTask, TaskSpec


class TaskFamily(ABC):
    @abstractmethod
    def prepare(self, spec: TaskSpec, seed: int, run_root) -> PreparedTask:
        raise NotImplementedError

    @abstractmethod
    def evaluate(
        self,
        prepared: PreparedTask,
        suite_weights: dict[str, float],
        duration_seconds: float,
        exit_code: int,
    ) -> Evaluation:
        raise NotImplementedError

    @staticmethod
    def make_prompt(title: str, overview: str, instructions: list[str], deliverables: list[str]) -> str:
        lines = [f"# {title}", "", overview, "", "## Instructions", ""]
        lines.extend(f"- {item}" for item in instructions)
        lines.extend(["", "## Deliverables", ""])
        lines.extend(f"- {item}" for item in deliverables)
        return "\n".join(lines) + "\n"

    @staticmethod
    def public_task_manifest(spec: TaskSpec, seed: int, deliverables: list[str], rules: list[str]) -> dict[str, Any]:
        return {
            "id": spec.id,
            "title": spec.title,
            "family": spec.family,
            "scenario": spec.scenario,
            "seed": seed,
            "difficulty": spec.difficulty,
            "description": spec.description,
            "tags": spec.tags,
            "budget": {
                "max_runtime_seconds": spec.budget.max_runtime_seconds,
                "max_tool_calls": spec.budget.max_tool_calls,
                "max_file_changes": spec.budget.max_file_changes,
            },
            "deliverables": deliverables,
            "rules": rules,
        }
