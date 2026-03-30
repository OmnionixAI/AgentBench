"""AgentBase — the native agent framework for AgentBench.

Provides standard primitives (BaseAgent, ExecutionContext) that make it trivial
to build an agent and wire it into the AgentBench CLI args.
"""

from agentbench.agentbase.agent import BaseAgent
from agentbench.agentbase.context import ExecutionContext, run_agent

__all__ = ["BaseAgent", "ExecutionContext", "run_agent"]
