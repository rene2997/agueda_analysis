from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .symstate import SymbolicState


@dataclass(slots=True)
class Finding:
    """
    Minimal stand-alone finding type.

    If your project already has a shared Finding abstraction,
    you can adapt this class or create adapter functions here.
    """
    kind: str
    message: str
    state: Optional[SymbolicState] = None
    model: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        return f"[{self.kind}] {self.message}"


@dataclass(slots=True)
class AssertionFailureFinding(Finding):
    pass


@dataclass(slots=True)
class DivideByZeroFinding(Finding):
    pass