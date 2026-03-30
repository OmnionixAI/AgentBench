"""Scenario loader — supports YAML and JSON suite files.

Transparently loads ``.yaml``/``.yml`` or ``.json`` suite definitions and
can merge multiple files from a directory into one SuiteSpec.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentbench.models import SuiteSpec


def load_scenario(path: Path) -> SuiteSpec:
    """Load a single ``.yaml`` or ``.json`` suite file."""
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        import yaml
        raw = yaml.safe_load(text)
    else:
        raw = json.loads(text)
    return _parse_suite(raw, source=str(path))


def load_scenario_dir(directory: Path) -> SuiteSpec:
    """Scan *directory* for ``.yaml``/``.yml``/``.json`` files and merge them."""
    files = sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix in (".yaml", ".yml", ".json")
    )
    if not files:
        raise FileNotFoundError(f"No scenario files found in {directory}")

    merged_tasks: list[dict[str, Any]] = []
    name = "AgentBench Combined Suite"
    version = "0.2.0"
    description = "Merged scenario suite."
    weights: dict[str, float] = {}

    for filepath in files:
        text = filepath.read_text(encoding="utf-8")
        if filepath.suffix in (".yaml", ".yml"):
            import yaml
            raw = yaml.safe_load(text)
        else:
            raw = json.loads(text)

        # Support both flat and nested formats
        suite_block = raw.get("suite", raw)
        if "name" in suite_block:
            name = suite_block["name"]
        if "version" in suite_block:
            version = suite_block["version"]
        if "description" in suite_block:
            description = suite_block["description"]
        file_weights = raw.get("weights", suite_block.get("weights", {}))
        if file_weights:
            weights.update(file_weights)

        tasks = raw.get("tasks", [])
        merged_tasks.extend(tasks)

    if not weights:
        weights = {"success": 0.55, "safety": 0.15, "recovery": 0.15, "efficiency": 0.10, "calibration": 0.05}

    return SuiteSpec.from_dict({
        "name": name,
        "version": version,
        "description": description,
        "weights": weights,
        "tasks": merged_tasks,
    })


def load_auto(path: Path) -> SuiteSpec:
    """Load from a file or directory, auto-detecting the format."""
    if path.is_dir():
        return load_scenario_dir(path)
    return load_scenario(path)


def _parse_suite(raw: dict[str, Any], source: str = "") -> SuiteSpec:
    """Parse a raw dict into a SuiteSpec, supporting both flat and nested YAML."""
    suite_block = raw.get("suite", raw)
    weights = raw.get("weights", suite_block.get("weights", {}))
    if not weights:
        weights = {"success": 0.55, "safety": 0.15, "recovery": 0.15, "efficiency": 0.10, "calibration": 0.05}

    return SuiteSpec.from_dict({
        "name": suite_block.get("name", "AgentBench Suite"),
        "version": suite_block.get("version", "0.2.0"),
        "description": suite_block.get("description", ""),
        "weights": weights,
        "tasks": raw.get("tasks", []),
    })
