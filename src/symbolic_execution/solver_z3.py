from __future__ import annotations
from typing import Dict, Any


from z3 import Solver as Z3Solver, Int, IntVal, BoolVal, Not, And, Or, sat
from .path import PathConstraint
from .symexpr import SymExpr, SymInt, SymBool, BinaryOp, SymArrayElem


class Solver:
    def __init__(self):
        self._elem_cache: dict[int, Any] = {}
        pass

    def is_sat(self, path: PathConstraint) -> bool:
        z3 = Z3Solver()
        for c in path.constraints:
            z3.add(self._to_z3(c))
        return z3.check().r == 1   # 1 = sat

    def get_model(self, path: PathConstraint) -> Dict[str, Any]:
        z3 = Z3Solver()
        for c in path.constraints:
            z3.add(self._to_z3(c))
        if z3.check().r != 1:
            return {}
        model = z3.model()

        out = {}
        for name, val in model:
            out[str(name)] = model[val].as_long()
        return out

    def _to_z3(self, expr: SymExpr):
        match expr:
            case SymInt():
                return self._z3_int(expr)
            case SymBool():
                return self._z3_bool(expr)
            case BinaryOp(op, lhs, rhs):
                return self._z3_binop(op, lhs, rhs)
            case ("not", inner):
                return Not(self._to_z3(inner))

        # --- ADD THIS BLOCK HERE ---
        # Array element → fresh integer (uninterpreted)
        if isinstance(expr, SymArrayElem):
            key = id(expr)
            if key not in self._elem_cache:
                self._elem_cache[key] = Int(f"{expr.array}_elem_{key}")
            return self._elem_cache[key]
        # --- END OF ADDED BLOCK ---

        raise NotImplementedError(f"Unsupported expression: {expr!r}")

    # Concrete or symbolic integer
    def _z3_int(self, v: SymInt):
        if v.concrete is not None:
            return IntVal(v.concrete)

        name = v.name if v.name is not None else f"x_{id(v)}"
        return Int(name)

    # Concrete or symbolic boolean
    def _z3_bool(self, v: SymBool):
        # If it’s a concrete Python bool, just wrap it
        if getattr(v, "concrete", None) is not None:
            return BoolVal(bool(v.concrete))

        # If it’s defined by some underlying expression, translate that
        expr = getattr(v, "expr", None)
        if expr is not None:
            return self._to_z3(expr)

        # Fallback: fresh boolean variable (should rarely happen)
        return Bool(f"b_{id(v)}")

    # Arithmetic + comparison operators
    def _z3_binop(self, op, lhs, rhs):
        zl = self._to_z3(lhs)
        zr = self._to_z3(rhs)

        # boolean relations
        if op == "==": return zl == zr
        if op == "!=": return zl != zr
        if op == "<":  return zl <  zr
        if op == "<=": return zl <= zr
        if op == ">":  return zl >  zr
        if op == ">=": return zl >= zr

        # arithmetic
        if op == "+":  return zl + zr
        if op == "-":  return zl - zr
        if op == "*":  return zl * zr
        if op == "//": return zl / zr         # integer division
        if op == "%":  return zl % zr

        raise NotImplementedError(f"Unknown binary op: {op}")