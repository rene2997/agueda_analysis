from __future__ import annotations

from typing import Dict, Any

from .path import PathConstraint
from .symexpr import SymExpr


class Solver:
    """
    Thin abstraction over an SMT solver (e.g. Z3).

    Right now this is a stub that always reports SAT.
    Later you plug in Z3 via z3-solver and translate expressions properly.
    """

    def is_sat(self, path: PathConstraint) -> bool:
        # TODO: translate `path` to an SMT formula and query the solver.
        return True

    def get_model(self, path: PathConstraint) -> Dict[str, Any]:
        """
        Return a satisfying assignment for symbolic input variables on this path.

        The keys are usually variable names ("x", "y", ...) and the values are
        concrete Python ints/bools.
        """
        # TODO: implement once Z3 integration is in place.
        return {}

    def eval_expr(self, expr: SymExpr, model: Dict[str, Any]) -> Any:
        """
        Evaluate an expression under a model (optional helper).
        """
        # TODO: Implement evaluation if needed for debugging/explanations.
        return None