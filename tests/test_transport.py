"""Tests for the MCP transport layer."""

from __future__ import annotations

import io
import unittest

from agentbench.transport.protocol import MCPMessage, MCPToolDefinition, MCPToolRegistry


class TestMCPMessage(unittest.TestCase):
    def test_request_round_trip(self) -> None:
        msg = MCPMessage.request("tools/list")
        self.assertTrue(msg.is_request())
        json_str = msg.to_json()
        restored = MCPMessage.from_json(json_str)
        self.assertEqual(restored.method, "tools/list")
        self.assertEqual(restored.id, msg.id)

    def test_response_round_trip(self) -> None:
        resp = MCPMessage.response("abc123", {"data": 42})
        self.assertTrue(resp.is_response())
        json_str = resp.to_json()
        restored = MCPMessage.from_json(json_str)
        self.assertEqual(restored.result, {"data": 42})
        self.assertIsNone(restored.error)

    def test_error_response(self) -> None:
        resp = MCPMessage.error_response("x1", -32601, "Not found")
        self.assertIsNotNone(resp.error)
        self.assertEqual(resp.error.code, -32601)
        d = resp.to_dict()
        self.assertEqual(d["error"]["code"], -32601)


class TestMCPToolRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = MCPToolRegistry()
        self.registry.register_simple("add", "Add two numbers", lambda args: args["a"] + args["b"])
        self.registry.register_simple("fail", "Always fails", lambda args: (_ for _ in ()).throw(ValueError("boom")))

    def test_list_tools(self) -> None:
        msg = MCPMessage.request("tools/list")
        resp = self.registry.dispatch(msg)
        self.assertIsNotNone(resp.result)
        tools = resp.result["tools"]
        names = [t["name"] for t in tools]
        self.assertIn("add", names)

    def test_call_tool_success(self) -> None:
        msg = MCPMessage.request("tools/call", {"name": "add", "arguments": {"a": 3, "b": 5}})
        resp = self.registry.dispatch(msg)
        self.assertEqual(resp.result["content"], 8)
        self.assertEqual(len(self.registry.call_log), 1)
        self.assertEqual(self.registry.call_log[0]["status"], "ok")

    def test_call_tool_not_found(self) -> None:
        msg = MCPMessage.request("tools/call", {"name": "nonexistent", "arguments": {}})
        resp = self.registry.dispatch(msg)
        self.assertIsNotNone(resp.error)
        self.assertEqual(resp.error.code, -32601)

    def test_call_log_records_errors(self) -> None:
        msg = MCPMessage.request("tools/call", {"name": "fail", "arguments": {}})
        resp = self.registry.dispatch(msg)
        self.assertIsNotNone(resp.error)
        self.assertEqual(self.registry.call_log[-1]["status"], "error")


class TestMCPToolDefinition(unittest.TestCase):
    def test_to_dict_and_from_dict(self) -> None:
        defn = MCPToolDefinition(name="my_tool", description="Does stuff", input_schema={"type": "object"})
        d = defn.to_dict()
        restored = MCPToolDefinition.from_dict(d)
        self.assertEqual(restored.name, "my_tool")
        self.assertEqual(restored.input_schema, {"type": "object"})


class TestStdioTransport(unittest.TestCase):
    def test_serve_processes_messages(self) -> None:
        from agentbench.transport.stdio import StdioTransport

        registry = MCPToolRegistry()
        registry.register_simple("echo", "Echo input", lambda args: args)

        msg = MCPMessage.request("tools/call", {"name": "echo", "arguments": {"text": "hello"}})
        input_stream = io.StringIO(msg.to_json() + "\n")
        output_stream = io.StringIO()

        StdioTransport.serve(registry, input_stream=input_stream, output_stream=output_stream)
        output_stream.seek(0)
        line = output_stream.readline()
        resp = MCPMessage.from_json(line)
        self.assertEqual(resp.result["content"], {"text": "hello"})


if __name__ == "__main__":
    unittest.main()
