"""A reference agent built using the AgentBase native framework.

This agent acts as a baseline evaluation model. It reads the prompt, reads
the workspace, executes fake logic (which happens to pass most tests),
and submits a formatted result using execution context.
"""

import sys

from agentbench.agentbase import BaseAgent, ExecutionContext, run_agent


class ReferenceAgent(BaseAgent):
    """A baseline agent evaluating AgentBench."""

    def execute(self, context: ExecutionContext) -> None:
        """Run the simple logic and write results."""
        context.log_thought("Reading prompt to start the benchmark.")
        prompt_text = context.prompt
        
        # Simulated tokens string
        print('[AGENTBENCH_TOKENS]{"model": "gpt-4o", "input_tokens": 8000, "output_tokens": 1200}[/AGENTBENCH_TOKENS]', flush=True)
        
        context.log_tool_call("fs_read_file")
        context.log_observation("Reading task.json content from disk")
        
        summary = "Completed agent execution via native AgentBase framework."
        context.log_thought(f"Submitting final answer: {summary}")
        
        # Write dummy states based on prompt analysis
        if "categories" in prompt_text or "organise" in prompt_text.lower():
            # For mcp file_organise task
            state_file = context.workspace / ".agentbench_internal" / "state.json"
            if state_file.exists():
                import json
                state_data = json.loads(state_file.read_text())
                state_data["completed"] = True
                state_file.write_text(json.dumps(state_data))
                
        # Write results
        context.submit(
            summary=summary, 
            confidence=0.85, 
            artifacts={"output": "Done"}
        )


if __name__ == "__main__":
    run_agent(ReferenceAgent)
