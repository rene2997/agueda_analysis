from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .symstate import SymbolicState


class WorklistStrategy(ABC):
    """
    Abstract interface for picking the next state to explore.
    """

    @abstractmethod
    def push(self, state: SymbolicState) -> None: ...

    @abstractmethod
    def pop(self) -> SymbolicState: ...

    @abstractmethod
    def empty(self) -> bool: ...


class DFSStrategy(WorklistStrategy):
    """
    Depth-First Search: use a simple stack.
    """

    def __init__(self) -> None:
        self._stack: List[SymbolicState] = []

    def push(self, state: SymbolicState) -> None:
        self._stack.append(state)

    def pop(self) -> SymbolicState:
        return self._stack.pop()

    def empty(self) -> bool:
        return not self._stack


class BFSStrategy(WorklistStrategy):
    """
    Breadth-First Search: use a FIFO queue.
    """

    def __init__(self) -> None:
        self._queue: List[SymbolicState] = []

    def push(self, state: SymbolicState) -> None:
        self._queue.append(state)

    def pop(self) -> SymbolicState:
        return self._queue.pop(0)

    def empty(self) -> bool:
        return not self._queue