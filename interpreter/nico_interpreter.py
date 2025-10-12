from unittest import case
import jpamb
from jpamb import jvm
from dataclasses import dataclass
import sys
from loguru import logger
from jpamb.jvm.opcode import Throw


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
class Frame:
    locals: dict[int, jvm.Value]
    stack: OperandStack
    pc: PC

    def __str__(self):
        locals = ", ".join(f"{k}:{v}" for k, v in sorted(self.locals.items()))
        return f"<{{{locals}}}, {self.stack}, {self.pc}>"

    def from_method(method: jvm.AbsMethodID) -> "Frame":
        return Frame({}, OperandStack.empty(), PC(method, 0))


@dataclass
class State:
    heap: dict[int, jvm.Value]
    frames: Stack[Frame]

    def __str__(self):
        return f"{self.heap} {self.frames}"


def step(state: State) -> State | str:
    assert isinstance(state, State), f"expected frame but got {state}"
    frame = state.frames.peek()
    opr = bc[frame.pc]
    print(f"@@COV {frame.pc.method} {frame.pc.offset}")
    logger.debug(f"STEP {opr}\n{state}")
    
    match opr:
        case jvm.Push(value=v):
            frame.stack.push(v)
            frame.pc += 1
            return state
        case jvm.Load(type=jvm.Int(), index=i):
            frame.stack.push(frame.locals[i])
            frame.pc += 1
            return state
        
        
        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Div):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"
            if v2.value == 0:
                return "divide by zero"
            frame.stack.push(jvm.Value.int(v1.value // v2.value))
            frame.pc += 1
            return state
        case jvm.Return(type=jvm.Int()): # return instruction for ints
            v1 = frame.stack.pop()
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                frame.stack.push(v1)
                frame.pc += 1
                return state
            else:
                return "ok"
        case jvm.Return(type=None): # return instruction for void
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                frame.pc += 1
                return state
            else:
                return "ok"
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
        
        # Adding case for jvm.binary operation
        case jvm.Binary(type=jvm.Int(), operant=op):
            v2 = frame.stack.pop()   # TOP
            v1 = frame.stack.pop()   # BELOW TOP
            assert v1.type == jvm.Int() and v2.type == jvm.Int()
            
            INT_MIN, INT_MAX = -(2**31), 2**31 - 1
            def _would_overflow(x): return x < INT_MIN or x > INT_MAX

            
            match op:
                case jvm.BinaryOpr.Add:
                    res = v1.value + v2.value
                    if _would_overflow(res):
                        print(f"@@FIND overflow {frame.pc.offset} {v1.value} {v2.value}")
                    frame.stack.push(jvm.Value.int(res))
                case jvm.BinaryOpr.Sub:
                    res = v1.value - v2.value
                    if _would_overflow(res):
                        print(f"@@FIND overflow {frame.pc.offset} {v1.value} {v2.value}")
                    frame.stack.push(jvm.Value.int(res))
                case jvm.BinaryOpr.Mul:
                    res = v1.value * v2.value
                    if _would_overflow(res):
                        print(f"@@FIND overflow {frame.pc.offset} {v1.value} {v2.value}")
                    frame.stack.push(jvm.Value.int(res))
                case jvm.BinaryOpr.Div:
                    if v2.value == 0:
                        print(f"@@FIND divzero {frame.pc.offset}")
                        return "divide by zero"
                    frame.stack.push(jvm.Value.int(v1.value // v2.value))
                case jvm.BinaryOpr.Rem:
                    if v2.value == 0:
                        print(f"@@FIND divzero {frame.pc.offset}")
                        return "divide by zero"
                    frame.stack.push(jvm.Value.int(v1.value % v2.value))
                case jvm.BinaryOpr.And:
                    frame.stack.push(jvm.Value.int(v1.value & v2.value))
                case jvm.BinaryOpr.Or:
                    frame.stack.push(jvm.Value.int(v1.value | v2.value))
                case jvm.BinaryOpr.Xor:
                    frame.stack.push(jvm.Value.int(v1.value ^ v2.value))
                case jvm.BinaryOpr.Shl:
                    frame.stack.push(jvm.Value.int(v1.value << v2.value))
                case jvm.BinaryOpr.Shr:
                    frame.stack.push(jvm.Value.int(v1.value >> v2.value))
                case jvm.BinaryOpr.Ushr:
                    frame.stack.push(jvm.Value.int((v1.value % 0x100000000) >> v2.value))
                case _:
                    raise NotImplementedError(str(op))
            frame.pc += 1
            return state
        
        
        
        case jvm.If(condition=c, target=t): # if condition for integers
            v2 = frame.stack.pop()   # TOP
            v1 = frame.stack.pop()   # BELOW TOP
            assert v1.type == jvm.Int() and v2.type == jvm.Int()

            match c:
                case "ne": jump = (v1.value != v2.value)
                case "eq": jump = (v1.value == v2.value)
                case "gt": jump = (v1.value >  v2.value)
                case "ge": jump = (v1.value >= v2.value)
                case "lt": jump = (v1.value <  v2.value)
                case "le": jump = (v1.value <= v2.value)
                case _:    raise NotImplementedError(str(c))

            if jump:
                frame.pc.offset = t
            else:
                frame.pc += 1
            return state
        case jvm.New(classname=c):
            
            return "assertion error"
        case jvm.Dup():
            v = frame.stack.pop()
            frame.stack.push(v)
            frame.stack.push(v)
            frame.pc += 1
            return state
        case a:
            a.help()
            raise NotImplementedError(f"Don't know how to handle: {a!r}")


logger.remove()
logger.add(sys.stderr, format="[{level}] {message}")

methodid, input = jpamb.getcase()
frame = Frame.from_method(methodid)
print(type(input), getattr(input, "__dict__", None))
print(type(input.values), input.values)
for i, v in enumerate(input.values):
    print(i, v, v.type, getattr(v, "value", None))
    match v:
        case jvm.Value(type=jvm.Reference()):
            pass
        case jvm.Value(type=jvm.Float()):
            pass
        case jvm.Value(type=jvm.Boolean(), value = value):
            v= jvm.Value.int(1 if value else 0)
        case jvm.Value(type=jvm.Int()):
            pass
        #case jvm.Value(type=jvm.Char()):
        case _:
            assert False, f"Do not know how to handle {v}"
    logger.debug(f"v has the value: {v}")
    frame.locals[i] = v

state = State({}, Stack.empty().push(frame))

for x in range(1000): # prevent infinite loop
    state = step(state)
    if isinstance(state, str):
        print(state)
        break
else:
    print("*")
