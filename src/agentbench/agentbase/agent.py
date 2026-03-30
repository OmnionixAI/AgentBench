"""Base agent framework."""

import abc

from agentbench.agentbase.context import ExecutionContext


class BaseAgent(abc.ABC):
    """Abstract base class for agents running natively inside AgentBench.

    To build your own agent, subclass this and implement the `execute` method.
    AgentBase will automatically handle CLI argument parsing, workspace paths,
    and structured JSON result submission.
    """

    @abc.abstractmethod
    def execute(self, context: ExecutionContext) -> None:
        """Execute the agent logic.

        Parameters
        ----------
        context : ExecutionContext
            Provides access to the `prompt`, `workspace`, and a `submit()` helper.
        """
        pass
