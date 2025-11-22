from __future__ import annotations

from time import time
from typing import List, Optional

from .config import SEConfig
from .findings import Finding
from .solver_z3 import Solver
from .strategy import DFSStrategy, BFSStrategy, WorklistStrategy
from .symstate import SymbolicState
from .jvm_frontend import JVMFrontend


class SymbolicExecutor:
    """
    High-level driver that:
      * Manages worklist/state exploration
      * Applies depth/state/time limits
      * Uses the JVMFrontend to step states
      * Optionally consults the solver for feasibility / models
    """

    def __init__(
        self,
        frontend: JVMFrontend,
        solver: Optional[Solver] = None,
        config: Optional[SEConfig] = None,
    ) -> None:
        self.frontend = frontend
        self.solver = solver or Solver()
        self.config = config or SEConfig()

        if self.config.strategy == "bfs":
            self.strategy: WorklistStrategy = BFSStrategy()
        else:
            self.strategy = DFSStrategy()

        self.findings: List[Finding] = []

    def run(self) -> List[Finding]:
        """
        Explore states starting from the entry method.

        Returns a list of collected findings (e.g., assertion failures, div-by-zero).
        """
        start_time = time()
        initial = self.frontend.initial_state(self.config)
        self.strategy.push(initial)

        explored = 0

        while not self.strategy.empty():
            if explored >= self.config.max_states:
                break
            if time() - start_time > self.config.timeout_seconds:
                break

            state = self.strategy.pop()
            explored += 1

            if state.terminated:
                continue

            # Simple depth control: use pc as a proxy, or extend state with a depth field.
            # For now we skip strict depth checks.
            successors = self.frontend.step(state)

            for succ in successors:
                if succ.error:
                    # Later you can create specific Finding subclasses based on error kind.
                    self.findings.append(Finding(kind="error", message=succ.error, state=succ))
                else:
                    self.strategy.push(succ)

        return self.findings