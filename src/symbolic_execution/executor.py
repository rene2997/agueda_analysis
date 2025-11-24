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
        
        steps = 0
        
        while worklist:
            state = self.strategy.next(worklist)
            assert isinstance(state, SymbolicState), f"Corrupted state: {state!r}"
            
            if self.config.debug:
                print(
                    f"[STEP {steps}] PC={state.pc} "
                    f"stack={state.stack} "
                    f"terminated={state.terminated} error={state.error} "
                    f"depth={state.path_constraint.depth()}",
                    flush=True,
                )
                
            # check the if reached maximum amount of steps
            if self.config.max_steps is not None and steps >= self.config.max_steps:
                if self.config.debug:
                    print(f"[STOP] Reached max_steps={self.config.max_steps}")
                break
            steps += 1
            
            if self.config.max_depth is not None:
                if state.path_constraint.depth() > self.config.max_depth:
                    continue
            
            # prune on depth
            if self.config.use_solver:
                if not self.solver.is_sat(state.path_constraint):
                    continue

            # if terminated record error/finding
            # if terminated record error/finding
            if state.terminated:
                if state.error is not None:
                    findings.append(Finding.from_state(state))
                    if self.config.debug:
                        print(
                            f"[FINDING] {state.error} at {state.pc} "
                            f"with {state.path_constraint}"
                        )
                continue

            # expand successor states using JVMFrontEnd
            successors = self.frontend.step(state)
            for succ in successors:
                assert isinstance(succ, SymbolicState), f"Frontend returned non-state: {succ!r}"
                self.strategy.add(worklist, succ)

        return findings