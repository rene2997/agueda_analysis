from __future__ import annotations
from typing import Any, List

from jpamb import jvm
from interpreter import PC, Bytecode
from .config import SEConfig
from .symexpr import SymInt, BinaryOp, SymArrayRef, SymArrayElem
from .symstate import SymbolicState

from .constraints import negate

def _add_int(val: SymInt, inc: int) -> SymInt:
    """
    Helper for iinc-style updates.
    Keeps integers concrete when possible and avoids building deep BinaryOp trees.
    """
    # If we have a concrete integer without a symbolic name, just fold it
    if isinstance(val, SymInt) and getattr(val, "concrete", None) is not None and getattr(val, "name", None) is None:
        return SymInt(concrete=val.concrete + inc)

    # Adding zero changes nothing
    if inc == 0:
        return val

    # Fallback: build a single BinaryOp node
    return BinaryOp("+", val, SymInt(concrete=inc))

class JVMFrontend:
    def __init__(self, bytecode: Bytecode, entry_method: jvm.AbsMethodID):
        self.bytecode = bytecode
        self.entry_method = entry_method

    def initial_state(self, config) -> SymbolicState:
        # Start at PC=0
        state = SymbolicState(pc=PC(self.entry_method, 0))
        state.depth = 0

        # ------------------------------------------------------------
        # Parse method descriptor from something like:
        #   "jpamb.cases.Arrays.arrayNotEmpty:([I)V"
        # ------------------------------------------------------------
        method_str = str(self.entry_method)
        try:
            desc = method_str.split(":", 1)[1]    # e.g. "([I)V"
        except IndexError:
            desc = "()V"

        # Extract inside parentheses
        if "(" in desc and ")" in desc:
            args_part = desc[desc.index("(") + 1 : desc.index(")")]
        else:
            args_part = ""

        i = 0
        local_index = 0

        # ------------------------------------------------------------
        # Parse argument types manually (JVM descriptor format)
        # ------------------------------------------------------------
        while i < len(args_part):
            ch = args_part[i]

            # -------- ARRAY ARGUMENT: [I, [C, [Z, [B ----------
            if ch == "[":
                # Assume 1D array; next char is element type
                if i + 1 < len(args_part):
                    elem_ch = args_part[i + 1]
                else:
                    elem_ch = "I"

                # Pick jpamb type for element
                if elem_ch == "I":
                    elem_type = jvm.Int()
                elif elem_ch == "C":
                    elem_type = jvm.Char()
                elif elem_ch == "Z":
                    elem_type = jvm.Boolean()
                else:
                    elem_type = jvm.Int()   # fallback

                # Make symbolic length for the array object
                len_sym = SymInt(name=f"len{local_index}")
                # Array lengths are non-negative
                state.path_constraint.add(BinaryOp(">=", len_sym, SymInt(concrete=0)))

                arr_id = f"arg{local_index}_arr"
                state.locals[arr_id] = {
                    "length": len_sym,
                    "type": elem_type,
                }

                # Local slot now holds a direct array reference (arguments are non-null)
                state.locals[local_index] = SymArrayRef(name=arr_id)
                
                
                # Move forward
                i += 2
                local_index += 1
                continue

            # -------- INTEGER ARGUMENT: I ----------
            if ch == "I":
                state.locals[local_index] = SymInt(name=f"arg{local_index}")
                i += 1
                local_index += 1
                continue

            # -------- BOOLEAN ARGUMENT: Z ----------
            if ch == "Z":
                # Represent boolean as 0/1 symbolic int
                state.locals[local_index] = SymInt(name=f"arg{local_index}")
                i += 1
                local_index += 1
                continue

            # -------- OTHER (unsupported) ----------
            i += 1

        return state

    # Wrapper around the actual step implementation.
    # Ensures we never return None. Depth is now managed by _step_impl
    # only for control-flow instructions (If/Ifz).
    def step(self, s: SymbolicState) -> list[SymbolicState]:
        s.steps += 1
        result = self._step_impl(s)
        if result is None:
            pc = PC(self.entry_method, s.pc)
            opcode = self.bytecode[pc]
            raise RuntimeError(
                f"Frontend.step() returned None at pc={s.pc}, opcode={opcode!r}"
            )

        # Depth is now managed inside `_step_impl` only for control‑flow
        # instructions (If/Ifz). For all other opcodes, the depth of
        # successor states is inherited from the parent.
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

        # 2. Look up opcode
        opr = self.bytecode[pc]

        # Current branching depth for this state; used to enforce a
        # bound on loop unfolding only at control‑flow instructions.
        parent_depth = getattr(s, "depth", 0)

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
                t = v.type

                # 1) Integer constants
                if isinstance(t, jvm.Int):
                    new.stack.append(SymInt(concrete=v.value))

                # 2) Boolean constants → 0/1
                elif isinstance(t, jvm.Boolean):
                    new.stack.append(SymInt(concrete=1 if v.value else 0))

                # 3) Character constants → map to integer code
                elif hasattr(jvm, "Char") and isinstance(t, jvm.Char):
                    # v.value is a Python string length 1
                    new.stack.append(SymInt(concrete=ord(v.value)))

                # 4) Null constant
                elif hasattr(jvm, "Null") and isinstance(t, jvm.Null):
                    # Null must have NO symbolic name
                    new.stack.append(SymInt(concrete=0, name=None))

                # 5) Any other constant-like payload
                else:
                    # Safest fallback: treat as an integer literal
                    val = getattr(v, "value", 0)
                    # Strings length 1 (chars)
                    if isinstance(val, str) and len(val) == 1:
                        val = ord(val)
                    # Non-int → fallback to 0
                    if not isinstance(val, int):
                        val = 0
                    new.stack.append(SymInt(concrete=val))

                # Proper PC advance
                new.pc = PC(method, offset + 1)
                return [new]

            case jvm.Return():
                new = s.copy()

                # Determine return value (if any)
                retval = None
                ret_type = getattr(opr, "type", None)
                if isinstance(ret_type, jvm.Int) and new.stack:
                    # Integer-returning method: pop symbolic result
                    retval = new.stack.pop()

                new.return_value = retval
                new.terminated = True
                # Normal termination is classified as "ok"
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

                # Increase branching depth only at this control‑flow point
                true_state.depth = parent_depth + 1
                false_state.depth = parent_depth + 1

                # Pop the value
                true_state.stack = true_state.stack[:-1]
                false_state.stack = false_state.stack[:-1]

                # Comparison with 0 / null
                zero = SymInt(concrete=0)  # concrete integer 0
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

                # Increase branching depth only at this control‑flow point
                true_state.depth = parent_depth + 1
                false_state.depth = parent_depth + 1

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
                ok_state.pc = PC(method, offset + 1)

                return [err_state, ok_state]
                
            case jvm.New(classname=c):
                new = s.copy()

                # Allocate a fresh, non-null reference for this object.
                # We model references as symbolic integers where 0 means null.
                ref_name = f"{c.slashed().replace('/', '_')}_ref_{len(new.locals)}"
                new.stack.append(SymInt(name=ref_name, concrete=1))

                # Just advance the program counter; the actual throwing of the
                # AssertionError is modeled by the Throw opcode.
                new.pc = PC(method, offset + 1)
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

                # Method descriptor as string, e.g. "jpamb.cases.Simple.assertBoolean:(Z)V"
                m_str = str(m)

                # Special-case the assertion helper used throughout JPAMB
                if "Simple.assertBoolean:(Z)V" in m_str:
                    # Top of stack is the boolean argument (0 = false, 1 = true)
                    cond_val = new.stack.pop()
                    zero = SymInt(concrete=0)

                    err_state = new.copy()
                    ok_state  = new.copy()

                    # cond_val == 0  -> assertion error
                    cond_expr = BinaryOp("==", cond_val, zero)

                    err_state.path_constraint.add(cond_expr)
                    err_state.terminated = True
                    err_state.error = "assertion error"

                    # cond_val != 0  -> ok, just continue
                    ok_state.path_constraint.add(negate(cond_expr))
                    ok_state.pc = PC(method, offset + 1)

                    return [err_state, ok_state]

                # All other static calls: best-effort no-op (ignore body)
                # If they pop arguments, we could parse the descriptor, but for Arrays
                # tests it is usually fine to just advance the PC.
                new.pc = PC(method, offset + 1)
                return [new]

            case jvm.InvokeSpecial(method=m, is_interface=_iface):
                new = s.copy()

                m_str = str(m)

                # Special-case AssertionError constructor used in compiled asserts.
                # Bytecode pattern is typically: new; dup; invokespecial <init>; athrow
                # After `dup`, the stack has [ref, ref]. The constructor call consumes
                # one receiver reference and returns void, so we pop exactly one ref
                # and keep the other for the subsequent `Throw`.
                if "java/lang/AssertionError.<init>:()V" in m_str:
                    if new.stack:
                        _this = new.stack.pop()
                    new.pc = PC(method, offset + 1)
                    return [new]

                # Default behaviour for other invokespecial calls: conservatively
                # pop a single receiver (if present) and advance. We ignore the
                # callee body and any arguments, which is sufficient for our tests.
                if new.stack:
                    _recv = new.stack.pop()

                new.pc = PC(method, offset + 1)
                return [new]
                
            case jvm.NewArray(type=t):
                new = s.copy()

                # Pop dimension (symbolic or concrete)
                dim = new.stack.pop()

                # symbolic arrays must have non-negative length
                ge_zero = BinaryOp(">=", dim, SymInt(concrete=0))
                new.path_constraint.add(ge_zero)
                new.path_constraint.add(BinaryOp(">=", dim, SymInt(concrete=0)))

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
                arr = new.stack.pop()

                # Case 1: concrete null
                if isinstance(arr, SymInt) and arr.concrete == 0:
                    err = s.copy()
                    err.terminated = True
                    err.error = "null pointer"
                    return [err]

                # Case 2: not an array reference
                if not isinstance(arr, SymArrayRef):
                    err = s.copy()
                    err.terminated = True
                    err.error = "*"
                    return [err]

                # Case 3: null stored in locals (no summary)
                if arr.name not in new.locals:
                    err = s.copy()
                    err.terminated = True
                    err.error = "null pointer"
                    return [err]

                # Case 4: OK path
                length = new.locals[arr.name]["length"]
                new.stack.append(length)
                new.pc = PC(method, offset + 1)
                return [new]

            case jvm.ArrayStore(type=t):
                # OK path: we'll refine its path_constraint depending on arr_ref
                new_ok = s.copy()

                # Pop value, index, array reference from OK branch
                val = new_ok.stack.pop()
                idx = new_ok.stack.pop()
                arr_ref = new_ok.stack.pop()

                zero = SymInt(concrete=0)

                # We may create extra error states
                error_states: list[SymbolicState] = []

                # -----------------------------------------
                # CASE 1: arr_ref is a SymArrayRef (heap array)
                # -----------------------------------------
                if isinstance(arr_ref, SymArrayRef):
                    arr_name = arr_ref.name

                # -----------------------------------------
                # CASE 2: arr_ref is a SymInt "argument reference"
                #         0  => null pointer
                #         !=0 => some argX_ref → lookup argX_arr
                # -----------------------------------------
                elif isinstance(arr_ref, SymInt):
                    # Concrete null from `Push Null`
                    # Null is ANY SymInt whose concrete value is 0
                    # even if it has a symbolic name by accident
                    if getattr(arr_ref, "concrete", None) == 0:
                        null_state = s.copy()
                        null_state.terminated = True
                        null_state.error = "null pointer"
                        return [null_state]

                    # Symbolic argument ref (0/≠0)
                    is_null = BinaryOp("==", arr_ref, zero)

                    null_state = s.copy()
                    null_state.path_constraint.add(is_null)
                    null_state.terminated = True
                    null_state.error = "null pointer"
                    error_states.append(null_state)

                    new_ok.path_constraint.add(negate(is_null))

                    refname = arr_ref.name
                    if refname is None or "_ref" not in refname:
                        bad = s.copy()
                        bad.terminated = True
                        bad.error = "*"
                        return [bad, *error_states]

                    arr_name = refname.replace("_ref", "_arr")

                # -----------------------------------------
                # CASE 3: unsupported reference type
                # -----------------------------------------
                else:
                    err = s.copy()
                    err.terminated = True
                    err.error = "*"
                    return [err]

                # -----------------------------------------
                # Lookup array summary
                # -----------------------------------------
                if arr_name not in new_ok.locals:
                    # We think it's non-null, but no summary -> null pointer / bad ref
                    err = s.copy()
                    err.terminated = True
                    err.error = "null pointer"
                    return [err, *error_states]

                arr_info = new_ok.locals[arr_name]
                length = arr_info["length"]   # SymInt

                # -------------------------
                # Bounds checks
                # -------------------------
                cond_ge_0  = BinaryOp(">=", idx, SymInt(concrete=0))
                cond_lt_len = BinaryOp("<", idx, length)

                # OK path: 0 <= idx < length
                new_ok.path_constraint.add(cond_ge_0)
                new_ok.path_constraint.add(cond_lt_len)
                new_ok.pc = PC(method, offset + 1)

                # Error paths: idx < 0  OR  idx >= length
                err_lo = s.copy()
                err_lo.path_constraint.add(negate(cond_ge_0))   # idx < 0
                err_lo.terminated = True
                err_lo.error = "out of bounds"

                err_hi = s.copy()
                err_hi.path_constraint.add(negate(cond_lt_len)) # idx >= length
                err_hi.terminated = True
                err_hi.error = "out of bounds"

                return [new_ok, err_lo, err_hi, *error_states]
                
            case jvm.ArrayLoad(type=t):
                new_ok = s.copy()
                zero = SymInt(concrete=0)

                # Pop index and array reference (stack order: ..., arrayref, index)
                idx = new_ok.stack.pop()
                arr_ref = new_ok.stack.pop()

                error_states: list[SymbolicState] = []

                # -----------------------------------------
                # 1) Null pointer checks
                # -----------------------------------------
                # Concrete null (pushed as 0)
                if isinstance(arr_ref, SymInt) and getattr(arr_ref, "concrete", None) == 0:
                    err = s.copy()
                    err.terminated = True
                    err.error = "null pointer"
                    return [err]

                # Argument-style reference: argX_ref -> argX_arr
                arr_name: str | None = None
                if isinstance(arr_ref, SymArrayRef):
                    arr_name = arr_ref.name
                elif isinstance(arr_ref, SymInt):
                    # Symbolic ref representing method argument: 0/null, !=0/non-null
                    refname = arr_ref.name
                    if refname is not None and "_ref" in refname:
                        arr_name = refname.replace("_ref", "_arr")
                    else:
                        # We don't know what this is; treat 0 vs non-zero:
                        is_null = BinaryOp("==", arr_ref, zero)

                        null_state = s.copy()
                        null_state.path_constraint.add(is_null)
                        null_state.terminated = True
                        null_state.error = "null pointer"
                        error_states.append(null_state)

                        new_ok.path_constraint.add(negate(is_null))

                        # And bail out if we can't map the reference to an array summary
                        if refname is None or "_ref" not in refname:
                            bad = s.copy()
                            bad.terminated = True
                            bad.error = "*"
                            return [bad, *error_states]

                        arr_name = refname.replace("_ref", "_arr")

                if arr_name is None:
                    # Unknown reference kind
                    err = s.copy()
                    err.terminated = True
                    err.error = "*"
                    return [err]

                # -----------------------------------------
                # 2) Lookup array summary
                # -----------------------------------------
                if arr_name not in new_ok.locals:
                    # Non-null but no array summary → treat as null pointer / bad ref
                    err = s.copy()
                    err.terminated = True
                    err.error = "null pointer"
                    return [err, *error_states]

                arr_info = new_ok.locals[arr_name]
                length = arr_info["length"]  # SymInt for array length

                # -----------------------------------------
                # 3) Generic arrays: keep full OOB modeling
                # -----------------------------------------
                cond_ge_0   = BinaryOp(">=", idx, zero)
                cond_lt_len = BinaryOp("<", idx, length)

                # OK path: 0 <= idx < length
                new_ok.path_constraint.add(cond_ge_0)
                new_ok.path_constraint.add(cond_lt_len)

                # Push a symbolic array element
                new_ok.stack.append(SymArrayElem(arr_name, idx))
                new_ok.pc = PC(method, offset + 1)

                # Error paths: idx < 0 and idx >= length
                err_lo = s.copy()
                err_lo.path_constraint.add(negate(cond_ge_0))   # idx < 0
                err_lo.terminated = True
                err_lo.error = "out of bounds"

                err_hi = s.copy()
                err_hi.path_constraint.add(negate(cond_lt_len)) # idx >= length
                err_hi.terminated = True
                err_hi.error = "out of bounds"

                return [new_ok, err_lo, err_hi, *error_states]
                    
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
                    # JVM default: uninitialized int local = 0
                    new.stack.append(SymInt(concrete=0))
                    new.pc = PC(method, offset + 1)
                    return [new]

                val = new.locals[i]
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
                ok_state.pc = PC(method, offset + 1)
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

                exc = None
                if new.stack:
                    exc = new.stack.pop()

                # Default classification
                error_label = "*"

                # If we know something about the thrown object, refine the label
                if isinstance(exc, SymInt):
                    ref_name = getattr(exc, "name", "") or ""

                    # Map by class name encoded in the reference name
                    if "AssertionError" in ref_name:
                        error_label = "assertion error"
                    elif "NullPointerException" in ref_name:
                        error_label = "null pointer"
                    elif "ArrayIndexOutOfBoundsException" in ref_name:
                        error_label = "out of bounds"
                    elif "ArithmeticException" in ref_name:
                        # Typically used for divide-by-zero etc.
                        error_label = "divide by zero"

                new.terminated = True
                new.error = error_label
                return [new]
            
            case jvm.Incr(index=idx, amount=inc):
                # iinc idx, inc  -- increment local variable idx by constant inc
                new = s.copy()

                # Get current value of local idx (default 0 if uninitialized)
                cur_val = new.locals.get(idx, SymInt(concrete=0))

                # Add the concrete increment (with light simplification)
                new.locals[idx] = _add_int(cur_val, inc)

                # Advance program counter
                new.pc = PC(method, offset + 1)
                return [new]
            
            case _:
                print("UNHANDLED OPCODE:", opr, "at", s.pc)
                new = s.copy()
                new.terminated = True
                new.error = "*"
                return [new]

