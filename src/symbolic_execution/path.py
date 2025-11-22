from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List

from .symexpr import SymBool


@dataclass(slots=True)
class PathConstraint:
    """
    A sequence of boolean constraints that must all hold on this path.
    E.g. [x > 0, x < 10, y == x + 1].

    Later, the solver translates this into an SMT formula.
    """
    constraints: List[SymBool] = field(default_factory=list)

    def add(self, cond: SymBool) -> None:
        self.constraints.append(cond)

    def extend(self, conds: Iterable[SymBool]) -> None:
        self.constraints.extend(conds)

    def copy(self) -> "PathConstraint":
        return PathConstraint(list(self.constraints))