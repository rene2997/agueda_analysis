import jpamb

import sys
import json
import os
from pathlib import Path

# ensure ../src is on sys.path so we can import interpreter
HERE = Path(__file__).resolve()
SRC_DIR = HERE.parents[1]   # .../agueda_analysis/src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from interpreter.interpreter import bc  # your existing Bytecode instance
from symbolic_execution.jvm_frontend import JVMFrontend
from symbolic_execution.executor import SymbolicExecutor
from symbolic_execution.solver_z3 import Solver
from symbolic_execution.config import SEConfig
from symbolic_execution.strategy import DFSStrategy
from symbolic_execution.symexpr import SymInt, BinaryOp, SymArrayRef, SymArrayElem
from symbolic_execution.symstate import SymbolicState


def expr_to_json(e):
    """Serialize a symbolic expression to a JSON-serializable dict."""
    if isinstance(e, SymInt):
        return {
            "kind": "symint",
            "name": e.name,
            "concrete": e.concrete,
        }
    if isinstance(e, BinaryOp):
        return {
            "kind": "binop",
            "op": e.op,
            "lhs": expr_to_json(e.lhs),
            "rhs": expr_to_json(e.rhs),
        }
    if isinstance(e, SymArrayRef):
        return {
            "kind": "arrayref",
            "name": e.name,
        }
    if isinstance(e, SymArrayElem):
        return {
            "kind": "arrayelem",
            "array": e.array_name,
            "index": expr_to_json(e.index),
        }

    # Fallback for anything unexpected
    return {
        "kind": "unknown",
        "repr": repr(e),
    }


def state_to_json(s: SymbolicState):
    """Serialize a SymbolicState to a JSON-serializable dict for the fuzzer."""
    # Serialize arguments: locals that look like arguments
    inputs = {}
    for idx, val in s.locals.items():
        if isinstance(val, SymInt):
            # Use the local index as key; the fuzzer can map this to JPAMB's arg ordering
            inputs[str(idx)] = expr_to_json(val)

    pc_method = None
    pc_offset = None
    if hasattr(s, "pc") and s.pc is not None:
        if hasattr(s.pc, "method"):
            pc_method = str(s.pc.method)
        if hasattr(s.pc, "offset"):
            pc_offset = s.pc.offset

    return {
        "terminated": getattr(s, "terminated", False),
        "error": getattr(s, "error", None),
        "pc": {
            "method": pc_method,
            "offset": pc_offset,
        },
        "path": [expr_to_json(c) for c in getattr(s, "path_constraint", [])],
        "inputs": inputs,
    }


def finding_to_json(f):
    """Serialize a Finding (kind + associated state, if present)."""
    state_json = None
    s = getattr(f, "state", None)
    if s is not None:
        state_json = state_to_json(s)

    return {
        "kind": f.kind,
        "state": state_json,
    }


def summarize(findings):
    from collections import Counter

    counts = Counter()
    for f in findings:
        k = f.kind
        if k is None:
            continue
        if k not in {"ok", "assertion error", "divide by zero", "out of bounds", "null pointer"}:
            k = "*"
        counts[k] += 1

    # Map “seen at all?” → 100%, otherwise 0%
    def score(label: str) -> int:
        return 100 if counts[label] > 0 else 0

    for label in ["assertion error", "ok", "*", "divide by zero", "out of bounds", "null pointer"]:
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

    # Optional JSON output for the fuzzer (concolic integration)
    # Enabled only when SE_JSON=1 to avoid breaking the JPAMB harness.
    if os.getenv("SE_JSON") == "1":
        payload = {
            "method": str(methodid),
            "findings": [finding_to_json(f) for f in findings],
        }
        print("SE_JSON_BEGIN")
        print(json.dumps(payload))
        print("SE_JSON_END")


if __name__ == "__main__":
    main()
