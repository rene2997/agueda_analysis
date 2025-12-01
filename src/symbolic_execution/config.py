from __future__ import annotations

from dataclasses import dataclass

MAX_ARRAY_LENGTH = 8
MAX_STEPS_PER_STATE = 300

@dataclass(slots=True)
class SEConfig:
    max_steps: int = 500      # allow more instructions per state
    max_depth: int = 50       # allow deeper branching (e.g. loop unrolls)
    max_states: int = 200     # optional: allow more simultaneous states
    timeout_seconds: float = 30.0
    strategy: str = "dfs"
    use_solver: bool = True
    debug: bool = False