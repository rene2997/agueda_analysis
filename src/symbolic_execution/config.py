from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SEConfig:
    """
    Configuration options for the symbolic execution engine.
    Adjust these defaults as you gain experience with the tool.
    """
    max_depth: int = 64
    max_states: int = 1000
    timeout_seconds: float = 5.0
    strategy: str = "dfs"  # "dfs" or "bfs" (used by executor/strategy.py)
    use_solver: bool = True