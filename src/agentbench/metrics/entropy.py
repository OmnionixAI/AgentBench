"""Tool-Selection Entropy metric.

Measures how consistently an agent picks the correct MCP tool when many
tools are available.  A perfect agent always selects the right tool and
never calls irrelevant ones, yielding entropy close to 0 (score → 1.0).
An agent that randomly explores the manifest scores near 0.0.
"""

from __future__ import annotations

import math
from collections import Counter


def tool_selection_entropy(
    tool_calls: list[str],
    correct_tools: set[str],
    total_available: int,
) -> float:
    """Return a normalised score in [0, 1] measuring tool-selection quality.

    Parameters
    ----------
    tool_calls:
        Ordered list of tool names the agent actually called.
    correct_tools:
        Set of tool names that were relevant/correct for the task.
    total_available:
        Total number of tools in the manifest (including decoys).

    Returns
    -------
    float
        1.0 = agent only called correct tools (perfect selection).
        0.0 = agent's call distribution is as spread-out as uniform random.
    """
    if not tool_calls or total_available <= 1:
        return 0.0

    counts = Counter(tool_calls)
    total_calls = len(tool_calls)

    # Shannon entropy of the agent's actual call distribution
    entropy = 0.0
    for count in counts.values():
        if count > 0:
            p = count / total_calls
            entropy -= p * math.log2(p)

    # Maximum entropy = uniform over all available tools
    max_entropy = math.log2(total_available) if total_available > 1 else 1.0

    # Normalised entropy: 0 = focused, 1 = maximally spread
    normalised = entropy / max_entropy if max_entropy > 0 else 0.0

    # Precision: fraction of calls that hit a correct tool
    correct_calls = sum(1 for call in tool_calls if call in correct_tools)
    precision = correct_calls / total_calls if total_calls > 0 else 0.0

    # Final score: blend of low-entropy (focused) and high-precision (accurate)
    # Both components are [0, 1].  Geometric mean rewards agents that are both.
    focus = max(0.0, 1.0 - normalised)
    score = math.sqrt(focus * precision)
    return round(max(0.0, min(1.0, score)), 4)
