from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SEConfig:
    """
    Configuration options for the symbolic execution engine.
    Adjust these defaults as you gain experience with the tool.
    """
    max_steps: int = 200
    max_depth: int = 40
    max_states: int = 100
    timeout_seconds: float = 10.0
    strategy: str = "dfs"  # "dfs" or "bfs" (used by executor/strategy.py)
    use_solver: bool = True
    debug: bool = False   