from __future__ import annotations

from typing import List
from .config import SEConfig, MAX_STEPS_PER_STATE
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

        steps = 0  # global step counter (for config.max_steps)

        while worklist:
            state = self.strategy.next(worklist)
            assert isinstance(state, SymbolicState), f"Corrupted state: {state!r}"

            # --- 1) Handle terminated states FIRST (but still prune UNSAT) ---
            if state.terminated:
                # Drop impossible terminated states (e.g. infeasible OOB / assertion branches)
                if self.config.use_solver:
                    if not self.solver.is_sat(state.path_constraint):
                        if self.config.debug:
                            print(
                                f"[PRUNE TERM] UNSAT terminated state at {state.pc} "
                                f"with {state.path_constraint}"
                            )
                        continue

                # If no specific error was set, treat this as a successful ("ok") path.
                label = state.error or "ok"

                state_for_finding = state.copy()
                state_for_finding.error = label
                findings.append(Finding.from_state(state_for_finding))
                if self.config.debug:
                    print(
                        f"[FINDING] {label} at {state.pc} "
                        f"with {state.path_constraint}"
                    )
                # Never explore successors of a terminated state
                continue

            # --- per-state bound ---
            if state.steps >= MAX_STEPS_PER_STATE:
                if self.config.debug:
                    print(
                        f"[PRUNE] Reached per-state step bound "
                        f"MAX_STEPS_PER_STATE={MAX_STEPS_PER_STATE} on state at PC={state.pc}"
                    )
                # Just drop this path: within our fuel limit we didn't see termination.
                # We do NOT classify it as '*' here to avoid polluting results
                # for finite programs like Arrays / Tricky.
                continue

            if self.config.debug:
                print(
                    f"[STEP {steps}] PC={state.pc} "
                    f"stack={state.stack} "
                    f"terminated={state.terminated} error={state.error} "
                    f"depth={state.path_constraint.depth()} "
                    f"steps_on_path={state.steps}",
                    flush=True,
                )

            # --- global exploration bound ---
            if self.config.max_steps is not None and steps >= self.config.max_steps:
                if self.config.debug:
                    print(f"[STOP] Reached max_steps={self.config.max_steps}")
                # Stop exploring, but don't turn all remaining states into '*'.
                worklist.clear()
                break

            steps += 1

            # --- depth bound ---
            if self.config.max_depth is not None:
                if state.path_constraint.depth() > self.config.max_depth:
                    if self.config.debug:
                        print(
                            f"[PRUNE-DEPTH] depth={state.path_constraint.depth()} "
                            f"> max_depth={self.config.max_depth} at PC={state.pc}"
                        )
                    # Over-depth paths are just dropped.
                    # They should not be counted as '*' either.
                    continue

            # --- prune on UNSAT for non-terminated states ---
            if self.config.use_solver:
                if not self.solver.is_sat(state.path_constraint):
                    if self.config.debug:
                        print(
                            f"[PRUNE] UNSAT non-terminated state at {state.pc} "
                            f"with {state.path_constraint}"
                        )
                    continue

            # --- expand successor states ---
            successors = self.frontend.step(state)

            # If frontend yields no successors but the state is not marked terminated,
            # treat it as an implicit normal return.
            if not successors:
                label = state.error or "ok"
                state_for_finding = state.copy()
                state_for_finding.error = label
                findings.append(Finding.from_state(state_for_finding))
                if self.config.debug:
                    print(
                        f"[FINDING-IMPLICIT] {label} at {state.pc} "
                        f"with {state.path_constraint}"
                    )
                continue

            for succ in successors:
                assert isinstance(succ, SymbolicState), \
                    f"Frontend returned non-state: {succ!r}"
                # increment per-state step count
                succ.steps = state.steps + 1
                self.strategy.add(worklist, succ)

        # --- After exploration: decide if we have a non-terminating method ---
        # If we never found ANY terminating path (no ok/assert/out-of-bounds/etc.),
        # interpret this as "looks non-terminating within our bounds" -> '*'.
        # This is exactly what we want for Loops.forever / neverAsserts / neverDivides.
        if not findings:
            cut = initial_state.copy()
            cut.terminated = True
            cut.error = "*"
            findings.append(Finding.from_state(cut))

        return findings