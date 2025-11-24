#!/usr/bin/env python3
from __future__ import annotations
import contextlib
import logging, argparse, platform, re
from pathlib import Path
import jpamb
from jpamb import jvm
from jpamb.model import Suite
from .core import Bytecode, Finding, AnalysisTool


class AssertTool:
    def analyze(self, m: Bytecode):
        saw_throw = False
        pc = None
        try:
            for op in m.ops:
                if isinstance(op, jvm.New) and "AssertionError" in str(
                    getattr(op, "classname", "")
                ):
                    saw_throw = True
                if isinstance(op, jvm.Throw) and saw_throw:
                    return [
                        Finding(
                            kind="assert", pc=getattr(op, "pc", -1), evidence="likely"
                        )
                    ]
        except Exception as e:
            return []
        return []


class DivZeroTool:
    def analyze(self, m: Bytecode):
        findings = []
        for op in m.ops:
            if isinstance(op, jvm.Binary):
                findings.append(
                    Finding(
                        kind="divzero",
                        pc=getattr(op, "pc", -1),
                        evidence="possible",
                    )
                )
        return findings


class NullTool:
    def analyze(self, m: Bytecode):
        pc = None
        for op in m.ops:
            if isinstance(op, jvm.Get) and not getattr(op, "static", True):
                return [Finding(kind="null", pc=getattr(op, "pc", -1), evidence="weak")]
            if isinstance(op, jvm.InvokeSpecial):
                return [Finding(kind="null", pc=getattr(op, "pc", -1), evidence="weak")]
            if isinstance(op, (jvm.ArrayLoad, jvm.ArrayStore)):
                return [Finding(kind="null", pc=getattr(op, "pc", -1), evidence="weak")]
        return []


class OOBTool:
    def analyze(self, m: Bytecode):
        pc = None
        findings = []
        for op in m.ops:
            if isinstance(op, (jvm.ArrayLoad, jvm.ArrayStore)):
                findings.append(Finding("oob", "weak"))
            if isinstance(op, jvm.New) and "ArrayIndexOutOfBoundsException" in str(
                getattr(op, "classname", "")
            ):
                findings.append(
                    Finding(kind="oob", pc=getattr(op, "pc", -1), evidence="certain")
                )
        return findings


class LoopTool:
    def analyze(self, m: Bytecode):
        pc = None
        has_exit = any(isinstance(op, (jvm.Return, jvm.Throw)) for op in m.ops)
        back_edge = False
        unconditional_back = False
        for idx, op in enumerate(m.ops):
            if isinstance(op, jvm.Goto):
                with contextlib.suppress(Exception):
                    if op.target < idx:
                        back_edge = True
                        unconditional_back = True
            if isinstance(op, (jvm.If, jvm.Ifz)):
                with contextlib.suppress(Exception):
                    if op.target < idx:
                        back_edge = True
        if unconditional_back and not has_exit:
            return [Finding(kind="loop", pc=getattr(op, "pc", -1), evidence="certain")]
        return (
            [Finding(kind="loop", pc=getattr(op, "pc", -1), evidence="weak")]
            if back_edge
            else []
        )
