from unittest import case
import jpamb
from jpamb import jvm
from dataclasses import dataclass
import sys
from loguru import logger
from abstractions import Sign, AState, PerVarFrame

MAX_ITERATIONS = 1000

@dataclass
class PC:
    method: jvm.AbsMethodID
    offset: int

    def __iadd__(self, delta):
        self.offset += delta
        return self

    def __add__(self, delta):
        return PC(self.method, self.offset + delta)

    def __str__(self):
        return f"{self.method}:{self.offset}"

@dataclass
class Bytecode:
    suite: jpamb.Suite
    methods: dict[jvm.AbsMethodID, list[jvm.Opcode]]

    def __getitem__(self, pc: PC) -> jvm.Opcode:
        try:
            opcodes = self.methods[pc.method]
        except KeyError:
            opcodes = list(self.suite.method_opcodes(pc.method))
            self.methods[pc.method] = opcodes

        return opcodes[pc.offset]

@dataclass
class Stack[T]:
    items: list[T]

    def __bool__(self) -> bool:
        return len(self.items) > 0

    @classmethod
    def empty(cls):
        return cls([])

    def peek(self) -> T:
        return self.items[-1]

    def pop(self) -> T:
        return self.items.pop(-1)

    def push(self, value):
        self.items.append(value)
        return self

    def __str__(self):
        if not self:
            return "ϵ"
        return "".join(f"{v}" for v in self.items)
    
class OperandStack(Stack[jvm.Value]):
    def push(self, value):
        return super().push(value)

suite = jpamb.Suite()
bc = Bytecode(suite, dict())

def step(state: AState) -> list[AState | str]:
    assert isinstance(state, AState), f"expected frame but got {state}"
    frame = state.frames.peek()
    opr = bc[frame.pc]
    print(f"@@COV {frame.pc.method} {frame.pc.offset}")
    logger.debug(f"STEP {opr}\n{state}")

    match opr:
        case jvm.Push(value=v):
            logger.debug(f"v in PUSH is: {v}")
            av = Sign.abstract(v.value)
            new = state.copy()
            newf = new.frames.peek()
            newf.stack.push(av)
            newf.pc += 1
            return [new]
        
        case jvm.Load(type=t, index=i):
            v = frame.locals[i]
            logger.debug(f"v in LOAD is: {v}")
            new = state.copy()
            newf = new.frames.peek()
            newf.stack.push(v)
            newf.pc += 1
            return [new]
        
        case jvm.Binary(operant=jvm.BinaryOpr.Div):
            new = state.copy()
            newf = new.frames.peek()
            v2 = newf.stack.pop()
            v1 = newf.stack.pop()
            logger.debug(f"frame.stack: {frame.stack}")
            logger.debug(f"v2: {v2}")
            logger.debug(f"v1: {v1}")

            for v in v2.values:
                if v == '0':
                    return ["divide by zero"]
            
            newf.stack.push(Sign.binary_op(v1, v2, Sign.sign_div))
            newf.pc += 1
            return [new]
        
        case jvm.Binary(operant=jvm.BinaryOpr.Sub):
            new = state.copy()
            newf = new.frames.peek()
            v2 = newf.stack.pop()
            v1 = newf.stack.pop()
            logger.debug(f"frame.stack: {frame.stack}")
            logger.debug(f"v2: {v2}")
            logger.debug(f"v1: {v1}")
            
            newf.stack.push(Sign.binary_op(v1, v2, Sign.sign_sub))
            newf.pc += 1
            return [new]
        
        case jvm.Return(type=t): # return instruction for void
            match t:
                case jvm.Int():
                    v1 = frame.stack.pop()
                    state.frames.pop()
                    if state.frames:
                        frame = state.frames.peek()
                        frame.stack.push(v1)
                        frame.pc += 1
                        return state
                    else:
                        #print("ok")
                        return ["ok"]
                case None:
                    state.frames.pop()
                    if state.frames:
                        frame = state.frames.peek()
                        frame.pc += 1
                        return state
                    else:
                        #print("ok")
                        return ["ok"]
                    
                case jvm.Reference():
                    v1 = frame.stack.pop()
                    state.frames.pop()
                    if state.frames:
                        frame = state.frames.peek()
                        frame.stack.push(v1)
                        frame.pc += 1
                        return state
                    else:
                        #print("ok")
                        return ["ok"]
            
        case jvm.Get(static=s, field=f): # only static int fields
            frame.stack.push(Sign.abstract(s)) #pushing s to the stack (which is basically a true)
            frame.pc += 1
            return state 
         
        case a:
            a.help()
            raise NotImplementedError(f"Don't know how to handle: {a!r}")
        
logger.remove()
logger.add(sys.stderr, format="[{level}] {message}")

methodid, input = jpamb.getcase()
frame = PerVarFrame.from_method(methodid)
print(type(input), getattr(input, "__dict__", None))
print(type(input.values), input.values)
for i, v in enumerate(input.values):
    print(i, v, v.type, getattr(v, "value", None))
    match v:
        case jvm.Value(type=jvm.Reference(value = value)):
            v = (Sign.abstract(value))

        case jvm.Value(type=jvm.Float(value = value)):
            v = (Sign.abstract(value))

        case jvm.Value(type=jvm.Boolean(), value = value):
            BoolToInt= 1 if value else 0
            v = (Sign.abstract({BoolToInt}))

        case jvm.Value(type=jvm.Int(), value= value):
            v = (Sign.abstract(value))

        case jvm.Value(type=jvm.Value(), value= value):
            v = (Sign.abstract(value.value))

        case jvm.Value(type=jvm.Array(), value = value):
            ArrayToReference = jvm.Value(jvm.Reference(), value) #our system only deals with int float and reference
            v = (Sign.abstract({ArrayToReference}))
        #case jvm.Value(type=jvm.Char()):
        case _:
            assert False, f"Do not know how to handle {v}"
    logger.debug(f"v has the value: {v}")
    frame.locals[i] = v

state = AState({}, Stack.empty().push(frame))

start_pc = state.frames.peek().pc.offset
analysis_map = {start_pc: state}
worklist = [start_pc] #the worklist is a todo list. when we find a new branch or update the interpreter, we add the pc of it's successor to the list
final = [] #holds final states
instruction_count = 0
while worklist:

    if instruction_count >= MAX_ITERATIONS:
        logger.warning(f"Analysis terminated: Fixed bound of {MAX_ITERATIONS} transitions reached.")
        break

    current_pc = worklist.pop(0)
    current_state = analysis_map[current_pc]

    successors = step(current_state)
    instruction_count += 1

    for succ in successors:
        if isinstance(succ, str):
            final.append(succ)
            continue

        succ_pc = succ.frames.peek().pc.offset
        old_state = analysis_map.get(succ_pc)

        if old_state is None:
            analysis_map[succ_pc] = succ
            worklist.append(succ_pc)
        else:
            new_joined_state = old_state.join(succ)
            if not new_joined_state.is_le(old_state):
                analysis_map[succ_pc] = new_joined_state
                worklist.append(succ_pc)

logger.debug(f"Total instructions executed: {instruction_count}")

if 'divide by zero' in final:
    print("divide by zero")
elif 'ok' in final:
    print("ok")
elif final:
    print(f"Analysis finished, encountered terminal states: {set(final)}")
else:
    print("Analysis terminated by reaching the fixed bound before finding a conclusive state.")

def number_of_args():
    return