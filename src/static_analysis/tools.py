#!/usr/bin/env python3
from __future__ import annotations
import contextlib
import logging, argparse, platform, re
from pathlib import Path
import jpamb
from jpamb import jvm
from jpamb.model import Suite
from .core import Bytecode, Finding, AnalysisTool
from .abstract_interpreter import create_initial_abstract_state, run_abstract_interpreter, bc, PerVarFrame, Stack, AState, jvm
from .abstractions import Sign

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


class AInTool:
    """
    Abstract Interpretation Tool.
    """
    def analyze(self, m: Bytecode) -> list[Finding]:
        print(f"--- [AInTool] Analyzing: {m.mid} ---")
        
        bc.methods[m.mid] = m.ops

        case_input = getattr(m, "case_input", None)
        initial_state = None

        if case_input is not None:
            print(f"[AInTool] Mode: Concrete Execution. Input: {case_input}")
            initial_state = create_initial_abstract_state(m.mid, case_input)
        else:
            print(f"[AInTool] Mode: Static Analysis. Initializing to TOP.")
            
            frame = PerVarFrame.from_method(m.mid)
            params = m.mid.extension.params 
            
            for i, param_type in enumerate(params):
                if isinstance(param_type, jvm.Boolean):
                    abstract_val = Sign.top() 
                elif isinstance(param_type, jvm.Int):
                    abstract_val = Sign.top()
                elif isinstance(param_type, jvm.Reference):
                    abstract_val = Sign.top() 
                else:
                    abstract_val = Sign.top()

                frame.locals[i] = abstract_val

            initial_state = AState({}, Stack.empty().push(frame))

        terminal_results = run_abstract_interpreter(initial_state, max_iterations=1000)
        print(f"[AInTool] Results: {terminal_results}")

        findings = []
        for result in set(terminal_results):
            if not isinstance(result, str): continue

            finding_kind = None
            if result == "divide by zero": finding_kind = "divzero"
            elif result == "assertion error": finding_kind = "assert"
            elif result == "out of bounds": finding_kind = "oob"
            elif result == "null pointer": finding_kind = "null"
            elif result == "*": finding_kind = "loop"

            if finding_kind:
                print(f"[AInTool] >>> FOUND ERROR: {finding_kind} <<<")
                findings.append(Finding(kind=finding_kind, pc=-1, evidence="certain"))

        return findings