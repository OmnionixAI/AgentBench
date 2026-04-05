from __future__ import annotations

from agentbench.families import AgenticReliabilityFamily, DataPipelineFamily, MCPToolUseFamily, RepoPatchFamily, ToolWorkflowFamily


def get_family(name: str):
    registry = {
        "repo_patch": RepoPatchFamily(),
        "data_pipeline": DataPipelineFamily(),
        "tool_workflow": ToolWorkflowFamily(),
        "mcp_tool_use": MCPToolUseFamily(),
        "agentic_reliability": AgenticReliabilityFamily(),
    }
    if name not in registry:
        raise KeyError(f"Unknown task family: {name}")
    return registry[name]
