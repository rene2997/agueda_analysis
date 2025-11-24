import jpamb

from interpreter.interpreter import bc  # your existing Bytecode instance
from symbolic_execution.jvm_frontend import JVMFrontend
from symbolic_execution.executor import SymbolicExecutor
from symbolic_execution.solver_z3 import Solver
from symbolic_execution.config import SEConfig
from symbolic_execution.strategy import DFSStrategy

def summarize(findings):
    from collections import Counter

    counts = Counter()
    for f in findings:
        k = f.kind
        if k is None:
            continue
        if k not in {"ok", "assertion error", "divide by zero", "out of bounds"}:
            k = "*"
        counts[k] += 1

    # Map “seen at all?” → 100%, otherwise 0%
    def score(label: str) -> int:
        return 100 if counts[label] > 0 else 0

    for label in ["assertion error", "ok", "*", "divide by zero", "out of bounds"]:
        print(f"{label}; {score(label)}%")
        


def main() -> None:
    # Let JPAMB set up method + info header
    methodid = jpamb.getmethodid(
        "symbolic-exec",          # analyzer name
        "0.1",                    # version
        "Your Group Name",        # group name
        ["symbolic", "python"],   # tags
        for_science=True,
    )

    # Hook up your symbolic engine
    frontend = JVMFrontend(bytecode=bc, entry_method=methodid)
    config = SEConfig()
    solver = Solver()
    strategy = DFSStrategy()

    print("DEBUG: use_solver =", config.use_solver)
    
    executor = SymbolicExecutor(
        frontend=frontend,
        config=config,
        solver=solver,
        strategy=strategy,
    )

    s0 = frontend.initial_state(config)
    findings = executor.run(s0)
    summarize(findings)


if __name__ == "__main__":
    main()