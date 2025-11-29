from __future__ import annotations

from dataclasses import dataclass

MAX_ARRAY_LENGTH = 8          # symbolic upper bound for array lengths
MAX_STEPS_PER_STATE = 100     # safety bound so states don't run forever

@dataclass(slots=True)
class SEConfig:
    """
    Configuration options for the symbolic execution engine.
    Adjust these defaults as you gain experience with the tool.
    """
    max_steps: int = 1000
    max_depth: int = 300
    max_states: int = 1000
    timeout_seconds: float = 10.0
    strategy: str = "dfs"  # "dfs" or "bfs" (used by executor/strategy.py)
    use_solver: bool = True
    debug: bool = False   