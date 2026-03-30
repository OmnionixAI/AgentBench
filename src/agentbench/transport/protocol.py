"""JSON-RPC 2.0 based MCP protocol primitives."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(slots=True)
class MCPError:
    code: int
    message: str
    data: Any = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MCPError":
        return cls(code=int(raw["code"]), message=str(raw["message"]), data=raw.get("data"))


@dataclass(slots=True)
class MCPMessage:
    """A single JSON-RPC 2.0 message."""

    id: str | None = None
    method: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: MCPError | None = None

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex[:12]

    def is_request(self) -> bool:
        return self.method is not None

    def is_response(self) -> bool:
        return self.result is not None or self.error is not None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": "2.0"}
        if self.id is not None:
            d["id"] = self.id
        if self.method is not None:
            d["method"] = self.method
            d["params"] = self.params
        if self.result is not None:
            d["result"] = self.result
        if self.error is not None:
            d["error"] = self.error.to_dict()
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MCPMessage":
        error = MCPError.from_dict(raw["error"]) if "error" in raw else None
        return cls(
            id=raw.get("id"),
            method=raw.get("method"),
            params=raw.get("params", {}),
            result=raw.get("result"),
            error=error,
        )

    @classmethod
    def from_json(cls, text: str) -> "MCPMessage":
        return cls.from_dict(json.loads(text))

    @classmethod
    def request(cls, method: str, params: dict[str, Any] | None = None) -> "MCPMessage":
        return cls(id=cls.new_id(), method=method, params=params or {})

    @classmethod
    def response(cls, id: str, result: Any) -> "MCPMessage":
        return cls(id=id, result=result)

    @classmethod
    def error_response(cls, id: str | None, code: int, message: str, data: Any = None) -> "MCPMessage":
        return cls(id=id, error=MCPError(code=code, message=message, data=data))


@dataclass(slots=True)
class MCPToolDefinition:
    """Description of a single tool the server exposes."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "MCPToolDefinition":
        return cls(
            name=raw["name"],
            description=raw.get("description", ""),
            input_schema=raw.get("inputSchema", raw.get("input_schema", {})),
        )


ToolHandler = Callable[[dict[str, Any]], Any]


class MCPToolRegistry:
    """Registry of MCP tools that can be served over any transport."""

    def __init__(self) -> None:
        self._tools: dict[str, MCPToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}
        self._call_log: list[dict[str, Any]] = []

    def register(self, definition: MCPToolDefinition, handler: ToolHandler) -> None:
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler

    def register_simple(
        self,
        name: str,
        description: str,
        handler: ToolHandler,
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        defn = MCPToolDefinition(name=name, description=description, input_schema=input_schema or {})
        self.register(defn, handler)

    def list_tools(self) -> list[MCPToolDefinition]:
        return list(self._tools.values())

    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        return name in self._handlers

    def manifest(self) -> list[dict[str, Any]]:
        return [tool.to_dict() for tool in self._tools.values()]

    @property
    def call_log(self) -> list[dict[str, Any]]:
        return list(self._call_log)

    def clear_log(self) -> None:
        self._call_log.clear()

    def dispatch(self, message: MCPMessage) -> MCPMessage:
        if message.method == "tools/list":
            return MCPMessage.response(message.id, {"tools": self.manifest()})

        if message.method == "tools/call":
            tool_name = message.params.get("name", "")
            arguments = message.params.get("arguments", {})
            if tool_name not in self._handlers:
                self._call_log.append({"tool": tool_name, "status": "not_found", "arguments": arguments})
                return MCPMessage.error_response(
                    message.id, -32601, f"Tool not found: {tool_name}"
                )
            try:
                result = self._handlers[tool_name](arguments)
                self._call_log.append({"tool": tool_name, "status": "ok", "arguments": arguments, "result": result})
                return MCPMessage.response(message.id, {"content": result})
            except Exception as exc:
                self._call_log.append({"tool": tool_name, "status": "error", "arguments": arguments, "error": str(exc)})
                return MCPMessage.error_response(message.id, -32000, str(exc))

        return MCPMessage.error_response(message.id, -32601, f"Unknown method: {message.method}")
