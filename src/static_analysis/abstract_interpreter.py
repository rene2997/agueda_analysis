from unittest import case
import jpamb
from jpamb import jvm
from dataclasses import dataclass
import sys
from loguru import logger

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
        assert value.type in [jvm.Int(), jvm.Float(), jvm.Reference()]
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
    

@dataclass
class Sign:
    values: set[str]
    @staticmethod
    def top():
        return Sign({"+", "-", "0"})
 
    def __le__(self, other) -> bool:
        return self.values <= other.values
 
    def join(self, other): #Also called or
        return Sign(self.values | other.values)
    
    def meet(self, other): #Also called and
        return Sign(self.values & other.values)
 
    @staticmethod
    def abstract(values: set[int]):
        return Sign(
            {"+" for v in values if v > 0}
            | {"-" for v in values if v < 0}
            | {"0" for v in values if v == 0}
        )
 
    def __contains__(self, value: int) -> bool:
        if value > 0:
            return "+" in self.values

        if value < 0:
            return "-" in self.values

        if value == 0:
            return "-" in self.values
        

@dataclass
class Parity:
    values: set[str]
    @staticmethod
    def top():
        return Parity({"even", "odd"})
 
    def __le__(self, other) -> bool:
        return self.values <= other.values
 
    def join(self, other):
        return Parity(self.values | other.values)
    
    def meet(self, other):
        return Parity(self.values & other.values) #use & because it's doing set logic not boolean logic
 
    @staticmethod
    def abstract(values: set[int]):
        return Parity(
            {"even" for v in values if (v % 2 == 0)}
            | {"odd" for v in values if (v % 2 == 1)}
        )
 
    def __contains__(self, value: int) -> bool:
        if v % 2 == 0:
            return "even" in self.values

        if v % 2 == 1:
            return "odd" in self.values


@dataclass
class Interval:
    start: int
    end: int
    @staticmethod
    def top():
        return Interval({-sys.maxsize, sys.maxsize})
    
    def bot():
        return Interval({sys.maxsize, -sys.maxsize})
 
    def __le__(self, other) -> bool:
        return self.start >= other.start and self.start <= other.values
 
    def join(self, other):
        start = min(self.start, other.start)
        end = max(self.end, other.end)
        return Interval(start, end)
    
    def meet(self, other):
        start = max(self.start, other.start)
        end = min(self.end, other.end)
        return Interval(start, end)
 
    @staticmethod
    def abstract(s, e):
        return Interval(
            start = s,
            end = e #should return [2,2] if it gets 2 as an input           
        )
 
    def __contains__(self, value: int) -> bool:
       if (self.start <= value) and (value <= self.end):
           return True
       else:
           return False
        
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
            frame.stack.push(v)
            frame.pc += 1
            return state

        case jvm.Get(static=s, field=f): # only static int fields
            frame.stack.push(jvm.Value.int(0)) #pushing s to the stack
            frame.pc += 1
            return state 

        case jvm.Boolean():
            frame.stack.push("Z")
            frame.pc += 1
            return state
        case jvm.Ifz(condition=c, target=t):
            v = frame.stack.pop()
            assert v.type == jvm.Int()
            match c:
                case "ne":
                    jump = v.value != 0
                case "eq":
                    jump = v.value == 0
                case "gt":
                    jump = v.value > 0
                case "ge":
                    jump = v.value >= 0
                case "lt":
                    jump = v.value < 0
                case "le":
                    jump = v.value <= 0
                case _:
                    raise NotImplementedError(str(c))
            if jump:
                frame.pc.offset = t
            else:
                frame.pc += 1
            return state 
        
        case jvm.Load(type=t, index=i):
            v = frame.locals[i]
            frame.stack.push(v)
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
            v = (Sign.abstract(value), Parity.abstract(value), Interval.abstract(value))
        case jvm.Value(type=jvm.Float(value = value)):
            v = (Sign.abstract(value), Parity.abstract(value), Interval.abstract(value))
        case jvm.Value(type=jvm.Boolean(), value = value):
            BoolToInt= 1 if value else 0
            v = (Sign.abstract({BoolToInt}), Parity.abstract({BoolToInt}), Interval.abstract(BoolToInt, BoolToInt))
        case jvm.Value(type=jvm.Int(), value= value):
            v = (Sign.abstract(value), Parity.abstract(value), Interval.abstract(value))

        case jvm.Value(type=jvm.Array(), value = value):
            ArrayToReference = jvm.Value(jvm.Reference(), value) #our system only deals with int float and reference
            v = (Sign.abstract({ArrayToReference}), Parity.abstract({ArrayToReference}), Interval.abstract({ArrayToReference}))
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