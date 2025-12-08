import jpamb
import sys
import json
import os
from pathlib import Path
# Path setup
HERE = Path(__file__).resolve() 
SRC_DIR = HERE.parents[1] # .../agueda_analysis/src
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
FUZZER_DIR = SRC_DIR / "fuzzer"
if str(FUZZER_DIR) not in sys.path:
    sys.path.insert(0, str(FUZZER_DIR))

# Try to import the fuzzer API entry point start_fuzzing
try:
    # Case 1: src/fuzzer/fuzzer_api.py
    from fuzzer_api import start_fuzzing  # type: ignore[import]
    _HAS_FUZZER = True
except Exception:
    try:
        # Case 2: src/fuzzer package with fuzzer_api module
        from fuzzer.fuzzer_api import start_fuzzing  # type: ignore[import]
        _HAS_FUZZER = True
    except Exception:
        start_fuzzing = None  # type: ignore[assignment]
        _HAS_FUZZER = False

from interpreter.interpreter import bc  # your existing Bytecode instance
from symbolic_execution.path import PathConstraint
from symbolic_execution.jvm_frontend import JVMFrontend
from symbolic_execution.executor import SymbolicExecutor
from symbolic_execution.solver_z3 import Solver
from symbolic_execution.config import SEConfig
from symbolic_execution.strategy import DFSStrategy
from symbolic_execution.symexpr import SymInt, BinaryOp, SymArrayRef, SymArrayElem
from symbolic_execution.symstate import SymbolicState


# Helpers: convert symbolic things -> JSON for fuzzer
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
    """Serialize a SymbolicState to a JSON-serializable dict for debugging."""
    inputs = {}
    for idx, val in s.locals.items():
        if isinstance(val, SymInt):
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


def compute_presence(findings):
    labels = ["assertion error", "ok", "*", "divide by zero", "out of bounds", "null pointer"]
    presence = {label: False for label in labels}
    for f in findings:
        k = getattr(f, "kind", None)
        if k is None:
            continue
        if k not in {"ok", "assertion error", "divide by zero", "out of bounds", "null pointer"}:
            k = "*"
        presence[k] = True
    return presence


def summarize(presence):
    labels = ["assertion error", "ok", "*", "divide by zero", "out of bounds", "null pointer"]
    for label in labels:
        score = 100 if presence.get(label, False) else 0
        print(f"{label}; {score}%")


# NEW: build guided_seeds for the fuzzer
from collections import defaultdict

def build_guided_seeds(method_str: str, findings, solver):
    """
    Build a payload for SE-guided fuzzing compatible with the fuzzer API.

    Returned structure:

        {
          "method": "jpamb.cases.Tricky.collatz:(I)V",
          "guided_seeds": [
              [v0_for_param0, v1_for_param0, ...],   # param 0 domain
              [v0_for_param1, v1_for_param1, ...],   # param 1 domain (if any)
              ...
          ]
        }

    So for a single-int method like collatz(int n), this would look like:
        "guided_seeds": [[0, 1, 5, ...]]

    Compared to the simple version, this tries to use the solver model for the
    *entry* symbolic variables (via the state.path_constraint) and only falls
    back to concrete locals if model-based extraction fails.
    """
    from collections import defaultdict

    print("SE_DEBUG: #findings =", len(findings), file=sys.stderr)

    # Collect a *set* of candidate values per local index (parameter position)
    per_param_values: dict[int, set[int]] = defaultdict(set)

    def _solve_path_constraint(state):
        """
        Best-effort helper: ask the solver for a model of this state's
        path_constraint. If anything goes wrong or no API matches, return None.
        """
        if solver is None:
            print("SE_DEBUG: no solver instance passed into build_guided_seeds", file=sys.stderr)
            return None

        raw_pc = getattr(state, "path_constraint", None)
        if raw_pc is None:
            print("SE_DEBUG:   no path_constraint on state; skipping solver", file=sys.stderr)
            return None

        # Normalize to a list of constraints
        if isinstance(raw_pc, PathConstraint):
            constraints = raw_pc.constraints
        elif isinstance(raw_pc, list):
            constraints = raw_pc
        else:
            # Single constraint object or unexpected type; wrap in a list
            constraints = [raw_pc]

        # If there are no constraints, there is nothing for the solver to do
        if not constraints:
            print("SE_DEBUG:   empty path_constraint; skipping solver", file=sys.stderr)
            return None

        try:
            length_info = f"len={len(constraints)}"
        except Exception:
            length_info = "len=?"
        print(
            f"SE_DEBUG:   solving path_constraint of type={type(raw_pc).__name__} ({length_info})",
            file=sys.stderr,
        )

        model = None
        try:
            # Solver exposes a 'get_model(pc)' style API taking a PathConstraint
            if hasattr(solver, "get_model"):
                pc_obj = PathConstraint(constraints)
                model = solver.get_model(pc_obj)
                print(f"SE_DEBUG:   solver.get_model(...) returned {type(model).__name__}", file=sys.stderr)
                print(f"SE_DEBUG:     model repr: {repr(model)}", file=sys.stderr)
                if isinstance(model, dict):
                    print(f"SE_DEBUG:     model keys: {list(model.keys())}", file=sys.stderr)
            # Solver exposes a 'solve(pc)' style API
            elif hasattr(solver, "solve"):
                pc_obj = PathConstraint(constraints)
                res = solver.solve(pc_obj)
                if isinstance(res, tuple) and len(res) >= 2:
                    sat, mdl = res[0], res[1]
                    print(f"SE_DEBUG:   solver.solve(...) -> (sat={sat}, model={type(mdl).__name__})", file=sys.stderr)
                    if bool(sat):
                        model = mdl
                        print(f"SE_DEBUG:     model repr: {repr(model)}", file=sys.stderr)
                        if isinstance(model, dict):
                            print(f"SE_DEBUG:     model keys: {list(model.keys())}", file=sys.stderr)
                else:
                    model = res
                    print(f"SE_DEBUG:   solver.solve(...) returned {type(model).__name__}", file=sys.stderr)
                    print(f"SE_DEBUG:     model repr: {repr(model)}", file=sys.stderr)
                    if isinstance(model, dict):
                        print(f"SE_DEBUG:     model keys: {list(model.keys())}", file=sys.stderr)
        except Exception as e:
            print(f"SE_DEBUG:   solver error while solving path_constraint: {e}", file=sys.stderr)
            model = None

        if model is None:
            print("SE_DEBUG:   no model obtained for this state", file=sys.stderr)
        return model

    def _value_from_model(sym: SymInt, model):
        """
        Try to extract an integer value for a SymInt from the solver model.
        This is deliberately defensive and will just return None if it can't
        figure it out, so that we can fall back to the old behaviour.
        """
        
        # First try to look up the SymInt's name directly in the model dict
        name = getattr(sym, "name", None)
        if name is not None and isinstance(model, dict):
            val = model.get(name)
            if val is not None:
                try:
                    return int(val)
                except Exception:
                    return val
        # … existing candidate_attrs logic …
        
        print(f"SE_DEBUG:   _value_from_model called for {sym} with model type={type(model).__name__}", file=sys.stderr)
        if model is None or not isinstance(sym, SymInt):
            return None

        # Common attribute names that might point to the underlying z3 variable
        candidate_attrs = ("var", "z3_var", "symbol", "z3", "expr")

        for attr in candidate_attrs:
            z = getattr(sym, attr, None)
            if z is None:
                continue

            # Try index or get-style access
            v = None
            try:
                v = model[z]
            except Exception:
                try:
                    v = model.get(z)  # type: ignore[call-arg]
                except Exception:
                    v = None

            if v is None:
                continue

            # Try to coerce to int
            try:
                # Z3-style ModelRef entry
                if hasattr(v, "as_long"):
                    val = int(v.as_long())
                    print(f"SE_DEBUG:   model gave {val} for {sym}", file=sys.stderr)
                    return val
            except Exception:
                pass

            try:
                iv = int(str(v))
                print(f"SE_DEBUG:   model(as str) gave {iv} for {sym}", file=sys.stderr)
                return iv
            except Exception:
                continue

        print(f"SE_DEBUG:   _value_from_model: no value found in model for {sym}", file=sys.stderr)
        return None

    for i, f in enumerate(findings):
        kind = getattr(f, "kind", None)
        state = getattr(f, "state", None)
        has_state = state is not None
        print(
            f"SE_DEBUG: finding[{i}] kind={kind!r} has_state={has_state}",
            file=sys.stderr,
        )

        if not has_state:
            continue

        locals_obj = getattr(state, "locals", {})
        if isinstance(locals_obj, dict):
            # Only show integer local indices (typically argument slots)
            int_keys = sorted(k for k in locals_obj.keys() if isinstance(k, int))
        else:
            int_keys = None
        print(
            "SE_DEBUG:   locals type="
            f"{type(locals_obj).__name__}, int_keys={int_keys}",
            file=sys.stderr,
        )

        if not isinstance(locals_obj, dict):
            continue

        # Try to get a model for this state's path_constraint
        model = _solve_path_constraint(state)

        # Only consider integer local indices (0,1,2,...) which map to parameters.
        int_indices = sorted(k for k in locals_obj.keys() if isinstance(k, int))

        # Only consider integer local indices (0,1,2,...) which map to parameters.
        int_indices = sorted(k for k in locals_obj.keys() if isinstance(k, int))

                # Only consider integer local indices (0,1,2,...) which map to parameters.
        int_indices = sorted(k for k in locals_obj.keys() if isinstance(k, int))

        for idx in int_indices:
            v = locals_obj[idx]
            candidate_val = None
            used_model = False

            param_name = f"arg{idx}"

            # Decide if this local *really* corresponds to a parameter.
            # Rule: it's a parameter if either
            #   - the solver model has a key "argN", or
            #   - it's a SymInt whose name is "argN".
            is_param = False
            if isinstance(model, dict) and param_name in model:
                is_param = True
            elif isinstance(v, SymInt) and getattr(v, "name", None) == param_name:
                is_param = True

            if not is_param:
                # Ignore non-parameter locals (loop counters, temporaries, etc.)
                continue

            # 1) Prefer the solver’s model value for argN
            if model is not None and isinstance(model, dict):
                model_val = model.get(param_name)
                if model_val is not None:
                    try:
                        candidate_val = int(model_val)
                    except Exception:
                        candidate_val = model_val
                    used_model = True

            # 2) Fallback: concrete value in the local (if SymInt or int)
            if candidate_val is None:
                if isinstance(v, SymInt) and v.concrete is not None:
                    candidate_val = int(v.concrete)
                elif isinstance(v, int):
                    candidate_val = int(v)

            if candidate_val is not None:
                print(
                    f"SE_DEBUG:   param {idx} -> candidate_val={candidate_val} "
                    f"(from {'model' if used_model else 'concrete'})",
                    file=sys.stderr,
                )
                per_param_values[idx].add(candidate_val)

    # After processing *all* findings
    print(
        f"SE_DEBUG: per_param_values="
        f"{ {idx: sorted(vals) for idx, vals in per_param_values.items()} }",
        file=sys.stderr,
    )

    # Turn each param's value set into a sorted list, ordered by param index
    guided_seed_domains: list[list[int]] = []
    for idx in sorted(per_param_values.keys()):
        vals = sorted(per_param_values[idx])
        guided_seed_domains.append(vals)

    return {
        "method": method_str,
        "guided_seeds": guided_seed_domains,
    }

# Main entry point used by JPAMB
def main() -> None:
    # Let JPAMB set up method + info header
    methodid = jpamb.getmethodid(
        "symbolic-exec",          # analyzer name
        "0.1",                    # version
        "Your Group Name",        # group name
        ["symbolic", "python"],   # tags
        for_science=True,
    )

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

    kind_counts = {}
    for f in findings:
        k = getattr(f, "kind", None)
        kind_counts[k] = kind_counts.get(k, 0) + 1
    print(f"SE_DEBUG: findings by kind = {kind_counts}", file=sys.stderr)

    presence = compute_presence(findings)

    # JSON output for concolic integration (what your teammate wants)
    method_str = str(methodid)
    guided_payload = build_guided_seeds(method_str, findings, solver)
    print(f"SE_DEBUG: guided_payload = {guided_payload}", file=sys.stderr)

    # This is the *exact* format the fuzzer side should consume:
    # {
    #   "method": "...",
    #   "guided_seeds": [ { ... }, ... ]
    # }
    if os.getenv("SE_GUIDED") == "1":
        print("SE_GUIDED_BEGIN")
        print(json.dumps(guided_payload))
        print("SE_GUIDED_END")

    # Optionally hand off to the fuzzer (if available)
    run_fuzzer_env = os.getenv("RUN_FUZZER")
    if run_fuzzer_env == "1":
        if not _HAS_FUZZER:
            # Fuzzer package not available; just warn on stderr and stop here.
            print(
                "SYMBEX: RUN_FUZZER=1 but fuzzer_api.start_fuzzing is not available; "
                "run pip/uv install or check your src/fuzzer package.",
                file=sys.stderr,
            )
        elif not guided_payload["guided_seeds"]:
            # No useful seeds from symbolic execution; nothing to guide with.
            print(
                "SYMBEX: RUN_FUZZER=1 but guided_seeds is empty; skipping fuzzing.",
                file=sys.stderr,
            )
        else:
            # Compute absolute paths so this works regardless of current working dir
            ROOT_DIR = SRC_DIR.parent  # .../agueda_analysis
            java_class_path = str(ROOT_DIR / "jpamb" / "target" / "classes")
            agent_path = str(SRC_DIR / "fuzzer" / "bytescribe-agent-1.0-SNAPSHOT.jar")

            print(
                f"SYMBEX: starting fuzzer for {guided_payload['method']} "
                f"with guided_seeds={guided_payload['guided_seeds']!r}",
                file=sys.stderr,
            )

            # Delegate to the shared fuzzer API. This will print its own summary,
            # including a FUZZER_RESULTS JSON blob, on stdout.
            results = start_fuzzing(
                target_method=guided_payload["method"],
                guided_seeds=guided_payload["guided_seeds"],
                java_class_path=java_class_path,
                agent_path=agent_path,
                max_iterations=10,
                seed_count=5,
                coverage_map_size=4096,
                print_summary=False,
            )

            if results:
                # Collect extra kinds derived from fuzzer crashes so JPAMB scoring
                # reflects bugs that only show up under fuzzing.
                extra_kinds = []
                crashes = results.get("crashes") or []
                for crash in crashes:
                    msg = (crash.get("error_message") or "").lower()
                    if "assert" in msg:
                        extra_kinds.append("assertion error")
                    elif "divide by zero" in msg or "arithmeticexception" in msg:
                        extra_kinds.append("divide by zero")
                    elif "null" in msg:
                        extra_kinds.append("null pointer")
                    

                # Mark these fuzzer-derived categories as seen
                for k in extra_kinds:
                    presence[k] = True

                # Print one compact summary line for the report/debug logging
                print(
                    "FUZZER_RESULTS:",
                    json.dumps(
                        {
                            "total_iterations": results.get("total_iterations"),
                            "corpus_size": results.get("corpus_size"),
                            "total_covered_branches": results.get("total_covered_branches"),
                            "crash_count": results.get("crash_count"),
                        }
                    ),
                )

                print(f"SE_DEBUG: combined presence after fuzzing = {presence}", file=sys.stderr)
                # Finally, print the JPAMB-style scoring line, combining
                # symbolic findings and fuzzer-derived kinds.
                summarize(presence)
                return

    # If we get here, either RUN_FUZZER != 1 or we had no fuzzer results;
    # fall back to pure symbolic-execution scoring.
    print(f"SE_DEBUG: presence from pure symbolic execution = {presence}", file=sys.stderr)
    summarize(presence)


if __name__ == "__main__":
    main()
