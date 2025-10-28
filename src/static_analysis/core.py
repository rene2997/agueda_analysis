# src/static_analysis/core.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Iterable, Optional
from jpamb import jvm


@dataclass
class Bytecode:
    mid: jvm.AbsMethodID
    ops: list[jvm.Opcode]
    cfg: Optional[object] = None


@dataclass
class Finding:
    kind: str
    pc: int
    evidence: str
    detail: Optional[str] = None


class AnalysisTool(Protocol):
    name: str

    def analyze(self, b: Bytecode) -> Iterable[Finding]: ...
