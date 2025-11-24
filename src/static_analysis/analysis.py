#!/usr/bin/env python3
from __future__ import annotations
import logging, argparse, platform, re
from pathlib import Path
import jpamb
from jpamb import jvm
from jpamb.model import Suite
from .core import Bytecode, Finding, AnalysisTool
from .tools import AssertTool, DivZeroTool, NullTool, OOBTool, LoopTool
import sys


logger = logging.getLogger(__name__)


def get_input(target: str):
    # Attempt to get input
    try:
        methodid, case_input = jpamb.getcase()
        return methodid, case_input
    # Else throw warning
    except Exception:
        logger.debug(f"Exception thrown for {target}")
        qclass, meth_part = target.rsplit(".", 1)
        method, desc = (meth_part.split(":", 1) + [None])[:2]
        cls = jvm.ClassName(qclass.replace(".", "/"))
        if desc:
            params, ret = _parse_descriptor(desc)
        else:
            params, ret = (jvm.ParameterType(tuple()), None)
        mid = jvm.AbsMethodID(cls, jvm.MethodID(method, params, ret))
        return mid, None


_PRIMS = {
    "I": jvm.Int,
    "Z": jvm.Boolean,
    "F": jvm.Float,
    "J": jvm.Long,
    "D": jvm.Double,
    "B": jvm.Byte,
    "S": jvm.Short,
    "C": jvm.Char,
}


def _parse_descriptor(desc: str):
    m = re.match(r"^\((.*)\)(.*)$", desc)
    if not m:
        raise ValueError(f"Bad descriptor: {desc}")
    psig, rsig = m.groups()

    def parse_types(sig: str):
        out, i = [], 0
        while i < len(sig):
            c = sig[i]
            if c in _PRIMS:
                out.append(_PRIMS[c]())
                i += 1
            elif c == "L":
                j = sig.index(";", i)
                out.append(jvm.Reference())
                i = j + 1
            elif c == "[":
                while i < len(sig) and sig[i] == "[":
                    i += 1
                if i < len(sig) and sig[i] == "L":
                    j = sig.index(";", i)
                    i = j + 1
                else:
                    i += 1
                out.append(jvm.Reference())
            else:
                raise ValueError(f"Unsupported type at {sig[i:]}")
        return out

    params = jvm.ParameterType(tuple(parse_types(psig)))
    ret = None if rsig == "V" else (_PRIMS.get(rsig, lambda: jvm.Reference())())
    return params, ret


KIND_MAP = {
    "assert": "assertion error",
    "divzero": "divide by zero",
    "oob": "out of bounds",
    "null": "null pointer",
    "loop": "*",
}

EVIDENCE_MAP = {
    "certain": "100%",
    "likely": "70%",
    "possible": "40%",
    "uncertain": "20%",
    "impossible": "0%",
}


class Analyzer:
    def __init__(self, args, src_root: Path | None):
        self.target = args.target
        self.src_root = src_root
        self.spec = None
        self.tools: list[AnalysisTool] = []

    def register(self, tool: AnalysisTool) -> None:
        self.tools.append(tool)

    def run_baseline(self):
        mid, _case_input = get_input(self.target)
        suite = Suite()
        ops = list(suite.method_opcodes(mid))
        # print("ops_ref:", ops)
        m = Bytecode(mid=mid, ops=ops, cfg=None)
        all_findings: list[Finding] = []
        for tool in self.tools:
            all_findings.extend(tool.analyze(m))
        self._emit_predictions(all_findings)

    def _emit_predictions(self, Fs: list[Finding]) -> None:
        evidences: dict[str, set[str]] = {}
        for f in Fs:
            evidences.setdefault(f.kind.strip().lower(), set()).add(
                f.evidence.strip().lower()
            )

        def pct(kind: str) -> str:
            evs = evidences.get(kind, set())
            for e in EVIDENCE_MAP:
                if e in evs:
                    return EVIDENCE_MAP[e]
            logger.warning(f"Evidence not set for kind {kind}")
            return "0%"

        keywords = ["assert"]
        flag = any(k in evidences for k in keywords)
        ok = "50%" if flag else "70%"

        def pr(label, val):
            print(f"{label};{val}")

        pr("ok", ok)
        pr("divide by zero", pct("divzero"))
        pr("assertion error", pct("assert"))
        pr("out of bounds", pct("oob"))
        pr("null pointer", pct("null"))
        pr("*", pct("loop"))

    def _split_target(self):
        try:
            return self.target.rsplit(".", 1)
        except ValueError as e:
            raise SystemExit(
                f"error: target must be pkg.Class.method[:desc] ({e})"
            ) from e

    def _split_method_desc(self, meth_part):
        return meth_part.split(":", 1) if ":" in meth_part else (meth_part, None)


def print_info():
    print("Baseline Static Analyzer")
    print("0.1.0")
    print("Group 5")
    print("static,syntactic")
    print(
        f"{platform.system()} {platform.release()} ({platform.machine()}), Python {platform.python_version()}"
    )


def setup_logging(debug: bool = False):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )
    logger.debug("Logging initialized (debug=%s)", debug)


def parse_args():
    parser = argparse.ArgumentParser("Baseline Static Analyzer")
    parser.add_argument("target", nargs="?", help="JPAMB qualname, or .class/.jar/dir")
    parser.add_argument(
        "--info", action="store_true", help="Print analyzer info and exit"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging(args.debug)

    if args.info:
        print_info()
        return

    analyzer = Analyzer(args, src_root=None)
    # ----- TO IMPLEMENT
    # ast = analyzer.parse_bytecode(args.target)
    # pc_map = analyzer.identify_hotspots(ast)
    # analyzer.set_pc_map(pc_map)
    # -----
    analyzer.register(LoopTool())
    analyzer.register(OOBTool())
    analyzer.register(AssertTool())
    analyzer.register(DivZeroTool())
    analyzer.register(NullTool())
    analyzer.run_baseline()


if __name__ == "__main__":
    main()
