from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .symstate import SymbolicState


@dataclass(slots=True)
class Finding:
    """
    Represents a discovered error path in symbolic execution.
    """
    kind: str
    pc: int
    path_constraint: Any
    return_value: Any = None

    @staticmethod
    def from_state(state: SymbolicState) -> "Finding":
        """
        Convert a terminated error state into a Finding.
        """
        return Finding(
            kind=state.error,
            pc=state.pc,
            path_constraint=state.path_constraint.copy(),
            return_value=getattr(state, "return_value", None),
        )

    def __repr__(self) -> str:
        return f"Finding(kind={self.kind}, pc={self.pc})"


@dataclass(slots=True)
class AssertionFailureFinding(Finding):
    pass


@dataclass(slots=True)
class DivideByZeroFinding(Finding):
    pass