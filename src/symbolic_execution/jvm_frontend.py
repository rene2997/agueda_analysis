from __future__ import annotations
from typing import Any, List
from unittest import case
from venv import logger
from jpamb import jvm
from interpreter import PC, Bytecode  
from .config import SEConfig
from .symexpr import SymInt, BinaryOp, SymArrayRef, SymArrayElem
from .symstate import SymbolicState 
from .constraints import negate

class JVMFrontend:
    def __init__(self, bytecode: Bytecode, entry_method: jvm.AbsMethodID):
        self.bytecode = bytecode
        self.entry_method = entry_method

    def initial_state(self, config) -> SymbolicState:
        # Start at PC=0 in the entry method
        state = SymbolicState(pc=PC(self.entry_method, 0))
        state.depth = 0

        #   - 0-arg methods just ignore them
        #   - 1-arg methods use locals[0]
        #   - 2-arg methods (like divideZeroByZero) use locals[0], locals[1]
        state.locals[0] = SymInt(name="arg0")
        state.locals[1] = SymInt(name="arg1")

        return state

    # added to prevent returning none from step() 
    def step(self, s: SymbolicState) -> list[SymbolicState]:
        result = self._step_impl(s)
        if result is None:
            pc = PC(self.entry_method, s.pc)
            opcode = self.bytecode[pc]
            raise RuntimeError(
                f"Frontend.step() returned None at pc={s.pc}, opcode={opcode!r}"
            )
        return result

    def _step_impl(self, s: SymbolicState):

        # 1. Normalize PC
        if isinstance(s.pc, int):
            method = self.entry_method
            offset = s.pc
        else:
            method = s.pc.method
            offset = s.pc.offset

        pc = PC(method, offset)

        # 2. Look up opcode  <-- THIS WAS MISSING
        opr = self.bytecode[pc]


        match opr:
            
            case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Sub):
                new = s.copy()
                rhs = new.stack.pop()
                lhs = new.stack.pop()
                new.stack.append(BinaryOp("-", lhs, rhs))
                new.pc = PC(method, offset + 1)
                return [new]
            
            
            case jvm.Push(value=v):
                new = s.copy()     
                match v.type:
                    case jvm.Int():
                        # push a concrete integer as a SymInt
                        new.stack.append(SymInt(concrete=v.value))

                    case jvm.Boolean():
                        # map booleans to 0/1, just like your concrete code does elsewhere
                        concrete = 1 if v.value else 0
                        new.stack.append(SymInt(concrete=concrete))

                    case _:
                        # For now, mark unsupported types as an error so we notice them
                        new.terminated = True
                        new.error = None
                        return [new]

                new.pc += 1
                return [new]
            
            case jvm.Return(type=jvm.Int()):
                new = s.copy()
                retval = new.stack.pop()
                new.terminated = True
                new.error = "ok"
                new.return_value = retval   # (optional but useful)

                return [new]
            
            case jvm.Return(type=None):
                new = s.copy()
                new.return_value = None
                new.terminated = True
                new.error = "ok"
                return [new]

            case jvm.Get(static=st, field=f):
                new = s.copy()  # now 's' is still the SymbolicState

                # Match concrete interpreter: static int fields → value 0
                new.stack.append(SymInt(concrete=0))

                new.pc = PC(method, offset + 1)
                return [new]
                
            case jvm.Boolean():
                new = s.copy()

                # create a symbolic boolean (integer 0/1)
                name = f"bool_{len(new.stack)}"
                new.stack.append(SymInt(name=name))

                new.pc = PC(method, offset + 1)
                return [new]

            case jvm.Ifz(condition=cond, target=target):
                if not s.stack:
                    new = s.copy()
                    new.terminated = True
                    new.error = "*"
                    return [new]

                value = s.stack[-1]

                true_state = s.copy()
                false_state = s.copy()

                # Pop the value
                true_state.stack = true_state.stack[:-1]
                false_state.stack = false_state.stack[:-1]

                # Comparison with 0 / null
                zero = SymInt(0)  # or however you represent literal 0
                op_map = {
                    "eq": "==",
                    "ne": "!=",
                    "lt": "<",
                    "ge": ">=",
                    "gt": ">",
                    "le": "<=",
                    "is": "==",      # null
                    "isnot": "!=",   # non-null
                }

                if cond not in op_map:
                    new = s.copy()
                    new.terminated = True
                    new.error = "*"
                    return [new]

                op = op_map[cond]
                cond_expr = BinaryOp(op, value, zero)

                true_state.path_constraint.add(cond_expr)
                false_state.path_constraint.add(negate(cond_expr))

                # Import once at top of file:
                # from jpamb.jvm.bytecode import PC

                method = s.pc.method
                true_state.pc = PC(method, target)
                false_state.pc = PC(method, s.pc.offset + 1)

                return [true_state, false_state]

            case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Add):
                new = s.copy()
                # Pop RHS (top) and LHS (below top)
                rhs = new.stack.pop()
                lhs = new.stack.pop()

                # Push symbolic sum
                new.stack.append(BinaryOp("+", lhs, rhs))

                new.pc = PC(method, offset + 1)
                return [new]
                    
            
            case jvm.If(condition=c, target=t):
                # Extract PC fields
                method = s.pc.method
                offset = s.pc.offset

                # Clone states
                true_state = s.copy()
                false_state = s.copy()

                # Operands
                rhs = s.stack[-1]
                lhs = s.stack[-2]

                # Translate JVM condition
                if c == "ne":
                    op = "!="
                elif c == "eq":
                    op = "=="
                elif c == "gt":
                    op = ">"
                elif c == "ge":
                    op = ">="
                elif c == "lt":
                    op = "<"
                elif c == "le":
                    op = "<="
                else:
                    raise NotImplementedError(f"Unknown If condition: {c}")

                cond_expr = BinaryOp(op, lhs, rhs)

                # Pop operands
                true_state.stack = true_state.stack[:-2]
                false_state.stack = false_state.stack[:-2]

                # Add constraints
                true_state.path_constraint.add(cond_expr)
                false_state.path_constraint.add(negate(cond_expr))

                # Jump vs fall-through
                true_state.pc = PC(method, t)
                false_state.pc = PC(method, offset + 1)

                return [true_state, false_state]
            
            case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Rem):
                # Integer remainder: lhs % rhs
                err_state = s.copy()
                ok_state = s.copy()

                rhs = s.stack[-1]  # divisor
                lhs = s.stack[-2]  # dividend
                zero = SymInt(concrete=0)

                # condition: rhs == 0  (mod by zero is also illegal)
                cond_expr = BinaryOp("==", rhs, zero)

                # Error branch: divide by zero
                err_state.stack = err_state.stack[:-2]
                err_state.path_constraint.add(cond_expr)
                err_state.terminated = True
                err_state.error = "divide by zero"

                # OK branch: symbolic remainder
                ok_state.stack = ok_state.stack[:-2]
                ok_state.stack.append(BinaryOp("%", lhs, rhs))
                ok_state.path_constraint.add(negate(cond_expr))
                ok_state.pc = s.pc + 1

                return [err_state, ok_state]
                
            case jvm.New(classname=c):
                new = s.copy()
                if c.slashed() == "java/lang/AssertionError":
                    new.terminated = True
                    new.error = "assertion error"
                    return [new]

                new.terminated = True
                new.error = f"unsupported new: {c.slashed()}"
                return [new]
                
            case jvm.Dup(words=w):
                new = s.copy()

                if not new.stack:
                    new.terminated = True
                    new.error = None
                    return [new]

                v = new.stack[-1]  # peek
                new.stack.append(v)  # duplicate symbolic expr

                new.pc = PC(method, offset + 1)
                return [new]
            
            
            case jvm.InvokeStatic(method=m):
                new = s.copy()
                new.terminated = True
                new.error = None
                return [new]
                
            case jvm.NewArray(type=t):
                new = s.copy()

                # Pop dimension (symbolic or concrete)
                dim = new.stack.pop()

                # symbolic arrays must have non-negative length
                # optionally add constraint dim >= 0

                # allocate a new heap array id
                arr_id = f"arr_{id(new)}_{len(new.locals)}"

                # store array summary in heap dict
                new.locals[arr_id] = {
                    "length": dim,   # SymInt
                    "type": t,       # jvm.Int(), jvm.Float(), jvm.Reference()
                }

                # push a symbolic reference to this array
                new.stack.append(
                    SymArrayRef(name=arr_id)
                )

                new.pc = PC(method, offset + 1)
                return [new]
                
            case jvm.ArrayLength():
                new = s.copy()

                # Pop symbolic array reference
                arr_ref = new.stack.pop()

                if not isinstance(arr_ref, SymArrayRef):
                    new.terminated = True
                    new.error = None
                    return [new]

                # Lookup array summary
                if arr_ref.name not in new.locals:
                    new.terminated = True
                    new.error = "null pointer"
                    return [new]

                arr_info = new.locals[arr_ref.name]

                # Extract symbolic length
                length = arr_info["length"]

                # Push symbolic length
                new.stack.append(length)

                # Advance PC
                new.pc = PC(method, offset + 1)
                return [new]

            case jvm.ArrayStore(type=t):
                # Make two copies for branching: OK path and OOB path
                new_ok = s.copy()
                new_err = s.copy()

                # Pop value, index, array reference from OK branch
                val = new_ok.stack.pop()
                idx = new_ok.stack.pop()
                arr_ref = new_ok.stack.pop()

                # TYPE CHECK: array reference must be symbolic
                if not isinstance(arr_ref, SymArrayRef):
                    new_err.terminated = True
                    new_err.error = None
                    return [new_err]

                # NULL CHECK: array summary must exist
                if arr_ref.name not in new_ok.locals:
                    new_err.terminated = True
                    new_err.error = "null pointer"
                    return [new_err]

                arr_info = new_ok.locals[arr_ref.name]
                length = arr_info["length"]     # symbolic length

                # -------------------------------------
                # Build in-bounds condition: 0 <= idx < length
                # -------------------------------------
                cond_ge_0 = BinaryOp(">=", idx, SymInt(concrete=0))
                cond_lt_len = BinaryOp("<", idx, length)

                # Add constraints to OK path
                new_ok.path_constraint.add(cond_ge_0)
                new_ok.path_constraint.add(cond_lt_len)
                new_ok.pc = s.pc + 1

                # Add negation to ERR path
                # (not >= 0) OR (not < length)
                new_err.path_constraint.add(negate(cond_ge_0))
                new_err.path_constraint.add(negate(cond_lt_len))
                new_err.terminated = True
                new_err.error = "out of bounds"

                return [new_ok, new_err]
                
            case jvm.ArrayLoad(type=t):
                # OK path and ERR path
                new_ok = s.copy()
                new_err = s.copy()

                # pop index and array reference
                idx = new_ok.stack.pop()
                arr_ref = new_ok.stack.pop()

                # type check: array reference must be symbolic
                if not isinstance(arr_ref, SymArrayRef):
                    new_err.terminated = True
                    new_err.error = f"ArrayLoad on non-array reference: {arr_ref}"
                    return [new_err]

                # null pointer?
                if arr_ref.name not in new_ok.locals:
                    new_err.terminated = True
                    new_err.error = "null pointer"
                    return [new_err]

                arr_info = new_ok.locals[arr_ref.name]
                length = arr_info["length"]    # symbolic length

                # -------------------------
                # Bounds checks
                # -------------------------
                cond_ge_0 = BinaryOp(">=", idx, SymInt(concrete=0))
                cond_lt_len = BinaryOp("<", idx, length)
                # OK path and ERR path
                new_ok = s.copy()
                new_err = s.copy()

                # pop index and array reference
                idx = new_ok.stack.pop()
                arr_ref = new_ok.stack.pop()

                # type check: array reference must be symbolic
                if not isinstance(arr_ref, SymArrayRef):
                    new_err.terminated = True
                    new_err.error = f"ArrayLoad on non-array reference: {arr_ref}"
                    return [new_err]

                # null pointer?
                if arr_ref.name not in new_ok.locals:
                    new_err.terminated = True
                    new_err.error = "null pointer"
                    return [new_err]

                arr_info = new_ok.locals[arr_ref.name]
                length = arr_info["length"]    # symbolic length

                # -------------------------
                # Bounds checks
                # -------------------------
                cond_ge_0 = BinaryOp(">=", idx, SymInt(concrete=0))
                cond_lt_len = BinaryOp("<", idx, length)

                # True path: index in bounds
                new_ok.path_constraint.add(cond_ge_0)
                new_ok.path_constraint.add(cond_lt_len)

                # Push symbolic element
                new_ok.stack.append(
                    SymArrayElem(arr_ref.name, idx)
                )

                new_ok.pc = s.pc + 1

                # Error path: out of bounds
                new_err.path_constraint.add(negate(cond_ge_0))
                new_err.path_constraint.add(negate(cond_lt_len))
                new_err.terminated = True
                new_err.error = "out of bounds"

                return [new_ok, new_err]
                
            case jvm.Cast(from_=f, to_=t):
                new = s.copy()
                new.pc = PC(method, offset + 1)
                return [new]
            
            case jvm.Goto(target=t):
                new = s.copy()
                new.pc = t
                return [new]
                
            case jvm.Store(type=t, index=i):
                new = s.copy()
                if not new.stack:
                    new.terminated = True
                    new.error = None
                    return [new]
                # Pop symbolic value
                val = new.stack.pop()
                # Write to locals
                new.locals[i] = val
                # Advance pc
                new.pc = PC(method, offset + 1)
                return [new]
                
            case jvm.Load(type=t, index=i):
                new = s.copy()
                if i not in new.locals:
                    new.terminated = True
                    new.error = None
                    return [new]
                val = new.locals[i]
                # push symbolic value onto stack
                new.stack.append(val)
                new.pc = PC(method, offset + 1)
                return [new]
            
            
            case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Div):
                # We symbolically branch on (rhs == 0)
                err_state = s.copy()
                ok_state = s.copy()

                # Use original stack to read operands
                rhs = s.stack[-1]  # divisor
                lhs = s.stack[-2]  # dividend
                zero = SymInt(concrete=0)

                # condition: rhs == 0
                cond_expr = BinaryOp("==", rhs, zero)

                err_state.stack = err_state.stack[:-2]   # pop lhs, rhs
                err_state.path_constraint.add(cond_expr)
                err_state.terminated = True
                err_state.error = "divide by zero"

                ok_state.stack = ok_state.stack[:-2]    # pop lhs, rhs
                ok_state.stack.append(BinaryOp("//", lhs, rhs))  # symbolic quotient
                ok_state.path_constraint.add(negate(cond_expr))
                ok_state.pc = s.pc + 1
                return [err_state, ok_state]

            case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Mul):
                new = s.copy()

                rhs = new.stack.pop()   # right operand
                lhs = new.stack.pop()   # left operand

                # Symbolic multiplication
                new.stack.append(BinaryOp("*", lhs, rhs))
                new.pc = PC(method, offset + 1)
                return [new]
                
                
            case jvm.Throw():
                new = s.copy()
                new.terminated = True
                new.error = "assertion error"
                return [new]
            
            case _:
                print("UNHANDLED OPCODE:", opr, "at", s.pc)
                new = s.copy()
                new.terminated = True
                new.error = "*"
                return [new]
