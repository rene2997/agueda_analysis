from symbolic_execution import SymbolicExecutor, SEConfig
from symbolic_execution.jvm_frontend import JVMFrontend
from symbolic_execution.solver_z3 import Solver


def main() -> None:
    # Dummy objects just to exercise constructors
    dummy_program = None
    dummy_entry = None
    frontend = JVMFrontend(dummy_program, dummy_entry)
    solver = Solver()
    config = SEConfig()

    executor = SymbolicExecutor(frontend=frontend, solver=solver, config=config)
    print("All symbolic_execution imports and constructors are OK.")


if __name__ == "__main__":
    main()