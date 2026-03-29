from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


CSI = "\033["


def supports_color() -> bool:
    return os.getenv("NO_COLOR") is None


def style(text: str, code: str) -> str:
    if not supports_color():
        return text
    return f"{CSI}{code}m{text}{CSI}0m"


def banner(title: str, subtitle: str | None = None) -> str:
    line = style(title, "1;36")
    if subtitle:
        line = f"{line}\n{style(subtitle, '0;37')}"
    return line


def key_value_block(values: dict[str, Any]) -> str:
    width = max(len(key) for key in values) if values else 0
    return "\n".join(f"{key.ljust(width)} : {value}" for key, value in values.items())


def render_table(headers: list[str], rows: list[list[Any]]) -> str:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(str(value)))
    header_line = "  ".join(str(value).ljust(widths[index]) for index, value in enumerate(headers))
    divider = "  ".join("-" * width for width in widths)
    body = [
        "  ".join(str(value).ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    ]
    return "\n".join([header_line, divider, *body])


def dump_json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def latest_summary_path(output_root: Path) -> Path | None:
    latest = output_root / "latest"
    summary = latest / "summary.json"
    return summary if summary.exists() else None
