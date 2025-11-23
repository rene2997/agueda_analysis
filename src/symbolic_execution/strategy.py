from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .symstate import SymbolicState


class WorklistStrategy(ABC):
    """
    Base strategy interface for symbolic execution.
    The executor calls:
       - init(initial_state)
       - next(worklist)
       - add(worklist, state)
       - empty(worklist)
    """

    @abstractmethod
    def init(self, initial: SymbolicState):
        ...

    @abstractmethod
    def next(self, worklist):
        ...

    @abstractmethod
    def add(self, worklist, state: SymbolicState):
        ...

    @abstractmethod
    def empty(self, worklist) -> bool:
        ...


class DFSStrategy(WorklistStrategy):
    """
    Depth-first search → stack
    """

    def init(self, initial: SymbolicState):
        return [initial]  # stack

    def next(self, worklist):
        return worklist.pop()  # LIFO

    def add(self, worklist, state: SymbolicState):
        worklist.append(state)
        return worklist

    def empty(self, worklist) -> bool:
        return len(worklist) == 0


class BFSStrategy(WorklistStrategy):
    """
    Breadth-first search → queue
    """

    def init(self, initial: SymbolicState):
        return [initial]  # queue

    def next(self, worklist):
        return worklist.pop(0)  # FIFO

    def add(self, worklist, state: SymbolicState):
        worklist.append(state)
        return worklist

    def empty(self, worklist) -> bool:
        return len(worklist) == 0