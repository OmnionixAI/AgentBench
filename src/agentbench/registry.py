from __future__ import annotations

from agentbench.families import DataPipelineFamily, RepoPatchFamily, ToolWorkflowFamily


def get_family(name: str):
    registry = {
        "repo_patch": RepoPatchFamily(),
        "data_pipeline": DataPipelineFamily(),
        "tool_workflow": ToolWorkflowFamily(),
    }
    if name not in registry:
        raise KeyError(f"Unknown task family: {name}")
    return registry[name]
