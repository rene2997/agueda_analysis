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
            continue  # completely ignore

        # Group any weird error strings into "*"
        if k not in {"ok", "assertion error", "divide by zero", "out of bounds"}:
            k = "*"

        counts[k] += 1

    total = sum(counts.values())
    if total == 0:
        # nothing interesting reached
        for label in ["assertion error", "ok", "*", "divide by zero", "out of bounds"]:
            print(f"{label};0%")
        return

    def pct(n):
        return int(round(100 * n / total))

    for label in ["assertion error", "ok", "*", "divide by zero", "out of bounds"]:
        print(f"{label};{pct(counts[label])}%")


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