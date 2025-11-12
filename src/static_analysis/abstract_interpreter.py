from unittest import case
import jpamb
from jpamb import jvm
from dataclasses import dataclass
import sys
from loguru import logger
from abstractions import Sign

MAX_ITERATIONS = 1000000

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

@dataclass
class PerVarFrame[AV]:
    locals: dict[int, AV]
    stack: Stack[AV]
    pc: PC

    def __str__(self):
        locals = ", ".join(f"{k}:{v}" for k, v in sorted(self.locals.items()))
        return f"<{{{locals}}}, {self.stack}, {self.pc}>"

    @classmethod
    def from_method(cls, method: jvm.AbsMethodID) -> "PerVarFrame":
        return PerVarFrame({}, OperandStack.empty(), PC(method, 0))

@dataclass
class AState[AV]:
    heap: dict[int, AV]
    frames: Stack[PerVarFrame]

    def __str__(self):
        return f"{self.heap} {self.frames}"
        
def many_step(state : dict[PC, AState | str]) -> dict[PC, AState | str]:
  new_state = dict(state)
  for k, v in state.items():
      for s in step(v):
        new_state[s.pc] |= s
  return new_state

def step(state: AState) -> AState | str:
    assert isinstance(state, AState), f"expected frame but got {state}"
    frame = state.frames.peek()
    opr = bc[frame.pc]
    #print(f"@@COV {frame.pc.method} {frame.pc.offset}")
    logger.debug(f"STEP {opr}\n{state}")

    match opr:
        case jvm.Push(value=v):
            logger.debug(f"v is: {v}")
            av = Sign.abstract(v.value)
            frame.stack.push(av)
            frame.pc += 1
            return state
        
        case jvm.Load(type=t, index=i):
            v = frame.locals[i]
            logger.debug(f"value being loaded is: {v}")
            frame.stack.push(v)
            frame.pc += 1
            return state
        
        case jvm.Binary(operant=jvm.BinaryOpr.Div):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            logger.debug(f"frame.stack: {frame.stack}")
            logger.debug(f"v2: {v2}")
            logger.debug(f"v1: {v1}")
            for v in v2.values:
                if v == '0':
                    return "divide by zero"
            frame.stack.push(Sign.binary_op(v1,v2,Sign.sign_div))
            frame.pc += 1
            return state
        
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
                        return "ok"
                case None:
                    state.frames.pop()
                    if state.frames:
                        frame = state.frames.peek()
                        frame.pc += 1
                        return state
                    else:
                        return "ok"
                case jvm.Reference():
                    v1 = frame.stack.pop()
                    state.frames.pop()
                    if state.frames:
                        frame = state.frames.peek()
                        frame.stack.push(v1)
                        frame.pc += 1
                        return state
                    else:
                        return "ok"
            
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

for x in range(MAX_ITERATIONS): # prevent infinite loop
    state = step(state)
    if isinstance(state, str):
        print(state)
        break
else:
    print("*")


def number_of_args():
    return

"""
@dataclass
class AbstractBool:
    values: set[bool]
    @staticmethod
    def top() -> Self:
        return AbstractBool({True, False})

    @staticmethod
    def __le__(self, other) -> bool:
        return self.values <= other.values
 
    @staticmethod
    def join(self, other) -> bool:
        return self.values | other.values
 
    @staticmethod
    def abstract(values: set[bool]) -> Self:
        return AbstractBool(values)
 
    def __contains__(self, value: int) -> bool:
        return value in self.values

000 | push:I 1
001 | load:I 0
002 | binary:I div
003 | return:I


 
n = Sign.top()
locals = [n]
stack = []
print(locals, stack)
# push:I 1
stack.append(Sign.abstract({1}))
print(locals, stack)
# load:I 0
stack.append(locals[0])
print(locals, stack)
# binary:I div

def binary_div(av1, av2):
    print(f"div: {av1=} {av2=}")
    outvalues = set()
    for x in av1.values:
        for y in av2.values:
            match (x, y):
                case ("+", "+"):
                    outvalues.add("+")
                case ("+", "-"):
                    outvalues.add("-")
                case ("+", "0"):
                    yield "divide by zero"
    yield Sign(outvalues)
for vals in binary_div(stack.pop(0), stack.pop(0)):
    print("!", vals)
print(locals, stack)

"""