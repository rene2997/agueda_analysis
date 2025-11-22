from __future__ import annotations
from typing import Any, List
from .config import SEConfig
from .symexpr import SymInt
from .symstate import SymbolicState


class JVMFrontend:
    def __init__(self, bytecode: Bytecode, entry_method: jvm.AbsMethodID):
        self.bytecode = bytecode
        self.entry_method = entry_method

    def initial_state(self, config) -> SymbolicState:
        # start at (method, offset=0), 1 symbolic int arg
        state = SymbolicState(pc=0)
        state.locals[0] = SymInt(name="arg0")
        return state

    def step(self, s: SymbolicState) -> list[SymbolicState]:
        pc = PC(self.entry_method, s.pc)
        opr = self.bytecode[pc]

        match opr:
            case jvm.Push(value=v):
                # like your concrete step, but using SymExpr
                ...
            case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Add):
                ...
            case jvm.If(condition=c, target=t):
                # fork: true + false, update path_constraint
                ...
            case jvm.Return(type=jvm.Int()):
                ...
            case _:
                ...