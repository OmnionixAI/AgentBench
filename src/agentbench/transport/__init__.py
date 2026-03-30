"""MCP transport layer for AgentBench.

Provides JSON-RPC 2.0 based communication between the benchmark harness
mock servers and the agent under test.  Supports stdio and HTTP transports.
"""

from agentbench.transport.protocol import (
    MCPError,
    MCPMessage,
    MCPToolDefinition,
    MCPToolRegistry,
)
from agentbench.transport.stdio import StdioTransport
from agentbench.transport.http import HttpTransport

__all__ = [
    "MCPError",
    "MCPMessage",
    "MCPToolDefinition",
    "MCPToolRegistry",
    "StdioTransport",
    "HttpTransport",
]
