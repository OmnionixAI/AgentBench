from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def sanitize_name(value: str) -> str:
    return value.replace(".", "_").replace(" ", "_").replace("-", "_")


def snapshot_tree(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(".agentbench_internal/"):
            continue
        if "/__pycache__/" in f"/{relative}/" or relative.endswith(".pyc"):
            continue
        files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    return [path for path in sorted(set(before) | set(after)) if before.get(path) != after.get(path)]


def float_round(value: float, places: int = 4) -> float:
    return round(float(value), places)


def stable_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
