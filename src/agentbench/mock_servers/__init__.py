"""Mock MCP servers for AgentBench evaluation scenarios.

Each server registers a set of tools into an MCPToolRegistry so the
agent under test must select the correct tool from a large manifest.
"""

from agentbench.mock_servers.filesystem import FilesystemServer
from agentbench.mock_servers.github import GitHubServer
from agentbench.mock_servers.slack import SlackServer
from agentbench.mock_servers.decoys import generate_decoy_tools

__all__ = [
    "FilesystemServer",
    "GitHubServer",
    "SlackServer",
    "generate_decoy_tools",
]
