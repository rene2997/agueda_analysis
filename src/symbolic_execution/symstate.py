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
    depth: int = 0
    terminated: bool = False
    error: Optional[str] = None
    return_value: Optional[Any] = None
    steps: int = 0

    
    def copy(self) -> "SymbolicState":
        return SymbolicState(
            pc=self.pc,
            stack=list(self.stack),
            locals=dict(self.locals),
            path_constraint=self.path_constraint.copy(),
            depth=self.depth,              
            terminated=self.terminated,
            error=self.error,
            return_value=self.return_value,
            steps=self.steps,              
        )