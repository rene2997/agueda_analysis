from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .symexpr import SymExpr
from .path import PathConstraint


@dataclass(slots=True)
class SymbolicState:
    """
    Represents the symbolic state of the JVM at some program point.

    - pc: program counter (bytecode index)
    - stack: operand stack
    - locals: local variables (JVM slots)
    - path_constraint: accumulated path condition
    - terminated: whether execution has finished on this path
    - error: optional error/violation description
    - return_value: (optional) value returned by this path, if any
    """
    pc: int
    stack: List[SymExpr] = field(default_factory=list)
    locals: Dict[int, SymExpr] = field(default_factory=dict)
    path_constraint: PathConstraint = field(default_factory=PathConstraint)
    terminated: bool = False
    error: Optional[str] = None
    return_value: Optional[Any] = None
    
    def copy(self) -> "SymbolicState":
        """
        Shallow copy of the state; symbolic expressions are immutable.
        """
        return SymbolicState(
            pc=self.pc,
            stack=list(self.stack),
            locals=dict(self.locals),
            path_constraint=self.path_constraint.copy(),
            terminated=self.terminated,
            error=self.error,
            return_value=self.return_value, 
        )