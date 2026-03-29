from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class AgentContext:
    task: dict[str, Any]
    workspace: Path
    result_file: Path
    prompt_file: Path | None = None


def load_context(task_file: str | Path, workspace: str | Path, result_file: str | Path, prompt_file: str | Path | None = None) -> AgentContext:
    task_path = Path(task_file)
    return AgentContext(
        task=json.loads(task_path.read_text(encoding="utf-8")),
        workspace=Path(workspace),
        result_file=Path(result_file),
        prompt_file=None if prompt_file is None else Path(prompt_file),
    )


def write_result(
    result_file: str | Path,
    summary: str,
    confidence: float,
    artifacts: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    payload: dict[str, Any] = {
        "summary": summary,
        "confidence": float(confidence),
        "artifacts": artifacts or [],
    }
    if extra:
        payload.update(extra)
    Path(result_file).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
