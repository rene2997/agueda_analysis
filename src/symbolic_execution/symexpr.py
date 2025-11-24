from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from typing import Any, Optional


class SymExpr(ABC):
    """
    Base class for all symbolic expressions (ints, bools, etc).

    At this stage it's just a tag type.
    The solver backend will later pattern-match on concrete subclasses.
    """
    pass

@dataclass(slots=True)
class SymArrayRef(SymExpr):
    name: str

    def __str__(self):
        return f"ArrayRef({self.name})"

@dataclass(slots=True)
class SymArrayElem(SymExpr):
    array: str
    index: SymExpr

    def __str__(self):
        return f"{self.array}[{self.index}]"

@dataclass(slots=True)
class SymInt(SymExpr):
    """
    A symbolic or concrete integer.

    - If `name` is not None, this represents a symbolic input variable, e.g. "x".
    - If `concrete` is not None, this holds a concrete known value.
    - It can be both (symbolic with a known example) if you want.
    """
    name: Optional[str] = None
    concrete: Optional[int] = None

    def __repr__(self) -> str:
        if self.name is not None and self.concrete is not None:
            return f"SymInt(name={self.name!r}, concrete={self.concrete})"
        if self.name is not None:
            return f"SymInt({self.name!r})"
        return f"SymInt(concrete={self.concrete})"


@dataclass(slots=True)
class SymBool(SymExpr):
    """
    A symbolic or concrete boolean.
    """
    expr: Any  # can later be a reference to a boolean AST node
    concrete: Optional[bool] = None

    def __bool__(self) -> bool:
        """
        Avoid accidental use in Python conditionals.
        Only allow if we truly have a concrete value.
        """
        if self.concrete is None:
            raise RuntimeError("Tried to use non-concrete SymBool in a Python 'if'.")
        return self.concrete


@dataclass(slots=True)
class BinaryOp(SymExpr):
    """
    Generic binary operator: lhs <op> rhs.

    The concrete semantics and SMT mapping will be provided
    by the solver backend.
    """
    op: str
    lhs: SymExpr
    rhs: SymExpr

    def __repr__(self) -> str:
        return f"({self.lhs!r} {self.op} {self.rhs!r})"