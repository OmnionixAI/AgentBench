from __future__ import annotations

from pathlib import Path

from agentbench.utils import ensure_dir


def write_python_adapter_template(output_path: Path) -> Path:
    ensure_dir(output_path.parent)
    output_path.write_text(_template(), encoding="utf-8")
    return output_path


def _template() -> str:
    return """from __future__ import annotations

import argparse
from pathlib import Path

from agentbench.adapters import load_context, write_result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--prompt", required=False)
    args = parser.parse_args()

    context = load_context(
        task_file=args.task,
        workspace=args.workspace,
        result_file=args.result,
        prompt_file=args.prompt,
    )

    task = context.task
    workspace = context.workspace

    # Replace this block with calls into your agent runtime.
    # The benchmark expects your agent to operate inside `workspace`
    # and then write a final agent_result.json via write_result(...).
    print(f"Running task {task['id']} in {workspace}")

    write_result(
        result_file=context.result_file,
        summary=f\"Stub adapter ran {task['id']} but did not solve it yet.\",
        confidence=0.10,
        artifacts=[],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""
