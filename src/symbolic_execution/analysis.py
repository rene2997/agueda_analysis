import jpamb

from interpreter.interpreter import bc  # reuse existing Bytecode
from jpamb import jvm

from symbolic_execution.jvm_frontend import JVMFrontend
from symbolic_execution.executor import SymbolicExecutor
from symbolic_execution.solver_z3 import Solver
from symbolic_execution.config import SEConfig
from symbolic_execution.strategy import DFSStrategy


def parse_method_sig(method_sig: str):
    """
    'jpamb.cases.Simple.divideByN:(I)I'
    -> classname 'jpamb/cases/Simple', name 'divideByN', desc '(I)I'
    """
    if ":" in method_sig:
        owner_and_name, desc = method_sig.split(":", 1)
    else:
        owner_and_name, desc = method_sig, "()V"

    class_fqn, name = owner_and_name.rsplit(".", 1)
    classname = class_fqn.replace(".", "/")
    return classname, name, desc


def main() -> None:
    # Let jpamb tell us which method/case to analyze
    methodid, expected = jpamb.getcase()

    # Reuse the global Bytecode instance from your concrete interpreter
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

    # One initial symbolic state for this method
    s0 = frontend.initial_state(config)
    findings = executor.run(s0)

    # Emit any findings in jpamb format
    for f in findings:
        print(f.to_jpamb())
 
 
    if __name__ == "__main__":
        main()