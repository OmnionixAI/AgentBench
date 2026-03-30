"""Tests for the native AgentBase framework."""

import json
import tempfile
import sys
import unittest
from pathlib import Path

from agentbench.agentbase import BaseAgent, ExecutionContext, run_agent


class TestAgent(BaseAgent):
    def execute(self, context: ExecutionContext) -> None:
        context.log_thought("Started executing test agent.")
        prompt_text = context.prompt
        if "FAIL_TEST" in prompt_text:
            context.log_error("Simulating a crash.")
            raise ValueError("Test failed intentionally.")
        
        context.submit(summary="Done", confidence=0.9)


def mock_run_agent(agent_cls, args_list) -> None:
    """Mock the runner substituting CLI args."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--prompt", type=Path)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--task-file", type=Path)
    
    args, _ = parser.parse_known_args(args_list)
    context = ExecutionContext(workspace=args.workspace, prompt_path=args.prompt, result_path=args.result)
    agent = agent_cls()
    agent.execute(context)


class TestAgentBase(unittest.TestCase):
    def test_execution_context_submit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            prompt = workspace / "prompt.txt"
            result = workspace / "result.json"
            prompt.write_text("Context prompt text", encoding="utf-8")
            
            ctx = ExecutionContext(workspace, prompt, result)
            self.assertEqual(ctx.prompt, "Context prompt text")
            
            ctx.submit(summary="Success", confidence=0.75, artifacts={"file": "test.txt"})
            self.assertTrue(result.exists())
            
            data = json.loads(result.read_text())
            self.assertEqual(data["summary"], "Success")
            self.assertEqual(data["confidence"], 0.75)
            self.assertEqual(data["artifacts"]["file"], "test.txt")
            
    def test_run_agent_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            prompt = workspace / "prompt.txt"
            result = workspace / "result.json"
            prompt.write_text("Do something", encoding="utf-8")
            
            args = [
                "--workspace", str(workspace),
                "--prompt", str(prompt),
                "--result", str(result),
            ]
            
            mock_run_agent(TestAgent, args)
            self.assertTrue(result.exists())
            data = json.loads(result.read_text())
            self.assertEqual(data["summary"], "Done")
            self.assertEqual(data["confidence"], 0.9)

    def test_run_agent_error_handling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            prompt = workspace / "prompt.txt"
            result = workspace / "result.json"
            prompt.write_text("FAIL_TEST", encoding="utf-8")
            
            args = [
                "--workspace", str(workspace),
                "--prompt", str(prompt),
                "--result", str(result),
            ]
            
            with self.assertRaises(ValueError):
                mock_run_agent(TestAgent, args)


if __name__ == "__main__":
    unittest.main()
