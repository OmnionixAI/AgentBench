"""Stdio transport for MCP — newline-delimited JSON over stdin/stdout."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TextIO

from agentbench.transport.protocol import MCPMessage, MCPToolRegistry


class StdioTransport:
    """Serve or connect to an MCP tool registry over stdin/stdout."""

    @staticmethod
    def serve(
        registry: MCPToolRegistry,
        input_stream: TextIO | None = None,
        output_stream: TextIO | None = None,
    ) -> None:
        """Blocking server loop — reads JSON lines from *input_stream*,
        dispatches to *registry*, writes responses to *output_stream*."""
        inp = input_stream or sys.stdin
        out = output_stream or sys.stdout
        for raw_line in inp:
            line = raw_line.strip()
            if not line:
                continue
            try:
                message = MCPMessage.from_json(line)
            except (json.JSONDecodeError, KeyError):
                resp = MCPMessage.error_response(None, -32700, "Parse error")
                out.write(resp.to_json() + "\n")
                out.flush()
                continue
            response = registry.dispatch(message)
            out.write(response.to_json() + "\n")
            out.flush()

    @staticmethod
    def connect(command: str | list[str]) -> "StdioClient":
        """Spawn *command* as a subprocess and return a client for sending
        MCP messages over its stdin/stdout."""
        if isinstance(command, str):
            import shlex
            command = shlex.split(command)
        proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return StdioClient(proc)


class StdioClient:
    """Client wrapper around a subprocess speaking MCP over stdio."""

    def __init__(self, process: subprocess.Popen) -> None:
        self._proc = process

    def send(self, message: MCPMessage) -> MCPMessage:
        assert self._proc.stdin is not None
        assert self._proc.stdout is not None
        self._proc.stdin.write(message.to_json() + "\n")
        self._proc.stdin.flush()
        raw = self._proc.stdout.readline()
        if not raw:
            return MCPMessage.error_response(message.id, -32000, "Server closed")
        return MCPMessage.from_json(raw.strip())

    def list_tools(self) -> list[dict]:
        msg = MCPMessage.request("tools/list")
        resp = self.send(msg)
        if resp.result and "tools" in resp.result:
            return resp.result["tools"]
        return []

    def call_tool(self, name: str, arguments: dict | None = None) -> MCPMessage:
        msg = MCPMessage.request("tools/call", {"name": name, "arguments": arguments or {}})
        return self.send(msg)

    def close(self) -> None:
        if self._proc.stdin:
            self._proc.stdin.close()
        self._proc.terminate()
        self._proc.wait(timeout=5)
