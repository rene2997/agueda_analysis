from __future__ import annotations

from typing import List
from .config import SEConfig
from .findings import Finding
from .solver_z3 import Solver
from .strategy import WorklistStrategy
from .symstate import SymbolicState
from .jvm_frontend import JVMFrontend


class SymbolicExecutor:
    """
    Main symbolic executor loop:
    - pulls states from the strategy’s worklist
    - prunes unsat / over-depth states
    - delegates JVM instruction semantics to JVMFrontend
    - collects Findings when terminated with errors
    """
    def __init__(
        self,
        frontend: JVMFrontend,
        config: SEConfig,
        solver: Solver,
        strategy: WorklistStrategy,
    ):
        self.frontend = frontend
        self.config = config
        self.solver = solver
        self.strategy = strategy

    def run(self, initial_state: SymbolicState) -> List[Finding]:
        worklist = self.strategy.init(initial_state)
        findings: List[Finding] = []

        while worklist:
            state = self.strategy.next(worklist)
            assert isinstance(state, SymbolicState), f"Corrupted state: {state!r}"
            # 1. Prune on depth
            if self.config.max_depth is not None:
                if state.path_constraint.depth() > self.config.max_depth:
                    continue

            # 2. Prune on UNSAT
            if not self.solver.is_sat(state.path_constraint):
                continue

            # 3. Terminated? Record error/finding
            if state.terminated:
                if state.error is not None:
                    findings.append(Finding.from_state(state))
                continue

            # 4. Expand successor states using JVMFrontEnd
            successors = self.frontend.step(state)
            for succ in successors:
                assert isinstance(succ, SymbolicState), f"Frontend returned non-state: {succ!r}"
                self.strategy.add(worklist, succ)

        return findings