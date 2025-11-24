from __future__ import annotations

from typing import Iterable

from .symexpr import SymBool, BinaryOp, SymExpr


def and_all(conds: Iterable[SymBool]) -> SymBool:
    """
    Build a conjunction of all constraints.
    For now this just builds a left-associated tree of BinaryOp("and", ...).
    """
    conds = list(conds)
    if not conds:
        # Empty conjunction is "true".
        return SymBool(expr=True, concrete=True)
    result: SymExpr = conds[0]
    for c in conds[1:]:
        result = BinaryOp("and", result, c)
    return SymBool(expr=result)


def negate(cond: SymBool) -> SymBool:
    """
    Negate a single boolean condition.
    The solver backend decides actual semantics.
    """
    return SymBool(expr=("not", cond), concrete=None)