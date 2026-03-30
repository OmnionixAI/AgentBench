"""HTTP transport for MCP — lightweight server using http.server."""

from __future__ import annotations

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from agentbench.transport.protocol import MCPMessage, MCPToolRegistry


def _make_handler(registry: MCPToolRegistry):
    """Factory returning a request handler class bound to *registry*."""

    class MCPHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002
            pass  # silence default stderr logging

        def do_GET(self):  # noqa: N802
            if self.path == "/mcp/tools":
                body = json.dumps({"tools": registry.manifest()}, sort_keys=True).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def do_POST(self):  # noqa: N802
            if self.path != "/mcp":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode()
            try:
                message = MCPMessage.from_json(raw)
            except (json.JSONDecodeError, KeyError):
                resp = MCPMessage.error_response(None, -32700, "Parse error")
                self._write_json(400, resp.to_dict())
                return
            response = registry.dispatch(message)
            status = 200 if response.error is None else 400
            self._write_json(status, response.to_dict())

        def _write_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return MCPHandler


class HttpTransport:
    """Serve an MCPToolRegistry over HTTP."""

    @staticmethod
    def serve(registry: MCPToolRegistry, host: str = "127.0.0.1", port: int = 0) -> "HttpServer":
        handler = _make_handler(registry)
        server = HTTPServer((host, port), handler)
        actual_port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return HttpServer(server, thread, host, actual_port)

    @staticmethod
    def connect(base_url: str) -> "HttpClient":
        return HttpClient(base_url.rstrip("/"))


class HttpServer:
    """Handle for a running HTTP MCP server."""

    def __init__(self, server: HTTPServer, thread: threading.Thread, host: str, port: int) -> None:
        self._server = server
        self._thread = thread
        self.host = host
        self.port = port

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def shutdown(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)


class HttpClient:
    """Client for calling an MCP server over HTTP."""

    def __init__(self, base_url: str) -> None:
        self._base = base_url

    def list_tools(self) -> list[dict]:
        req = urllib.request.Request(f"{self._base}/mcp/tools")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return data.get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> MCPMessage:
        msg = MCPMessage.request("tools/call", {"name": name, "arguments": arguments or {}})
        body = msg.to_json().encode()
        req = urllib.request.Request(
            f"{self._base}/mcp",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
        return MCPMessage.from_json(raw)

    def send(self, message: MCPMessage) -> MCPMessage:
        body = message.to_json().encode()
        req = urllib.request.Request(
            f"{self._base}/mcp",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
        return MCPMessage.from_json(raw)
