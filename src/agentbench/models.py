from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Budget:
    max_runtime_seconds: int = 120
    max_tool_calls: int | None = None
    max_file_changes: int | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Budget":
        return cls(
            max_runtime_seconds=int(raw.get("max_runtime_seconds", 120)),
            max_tool_calls=raw.get("max_tool_calls"),
            max_file_changes=raw.get("max_file_changes"),
        )


@dataclass(slots=True)
class TaskSpec:
    id: str
    title: str
    family: str
    scenario: str
    difficulty: str
    description: str
    tags: list[str]
    default_seeds: list[int]
    budget: Budget

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "TaskSpec":
        return cls(
            id=raw["id"],
            title=raw["title"],
            family=raw["family"],
            scenario=raw["scenario"],
            difficulty=raw["difficulty"],
            description=raw["description"],
            tags=list(raw.get("tags", [])),
            default_seeds=[int(seed) for seed in raw.get("default_seeds", [])],
            budget=Budget.from_dict(raw.get("budget", {})),
        )


@dataclass(slots=True)
class SuiteSpec:
    name: str
    version: str
    description: str
    weights: dict[str, float]
    tasks: list[TaskSpec]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SuiteSpec":
        return cls(
            name=raw["name"],
            version=raw["version"],
            description=raw["description"],
            weights={key: float(value) for key, value in raw["weights"].items()},
            tasks=[TaskSpec.from_dict(task) for task in raw["tasks"]],
        )


@dataclass(slots=True)
class PreparedTask:
    spec: TaskSpec
    seed: int
    workspace: Path
    prompt_path: Path
    task_file: Path
    result_file: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Evaluation:
    scores: dict[str, float | None]
    overall: float
    passed: bool
    notes: list[str]
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EpisodeResult:
    task_id: str
    seed: int
    run_label: str
    workspace: Path
    duration_seconds: float
    exit_code: int
    stdout_path: Path
    stderr_path: Path
    evaluation: Evaluation
