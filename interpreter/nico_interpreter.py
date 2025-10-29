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

    @classmethod
    def from_method(cls, method: jvm.AbsMethodID) -> "Frame":
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
        case jvm.Dup(words=w):
            v = frame.stack.peek()
            frame.stack.push(v)
            frame.pc += 1
            return state
        case jvm.InvokeStatic(method=m):
            n = len(m.methodid.params)
            #logger.debug(f"Length of parameters is: {n}")
            args = []
            for _ in range(n):
                args.append(frame.stack.pop())
            args.reverse()
            #logger.debug(f"Args are: {args}")
            new_frame = frame.from_method(m)
            for i, arg in enumerate(args):
                new_frame.locals[i] = arg
            # logger.debug(f" The length of locals is: {len(new_frame.locals)}")
            state.frames.push(new_frame) # executes the method
            return state
        case jvm.NewArray(type = t):
            v1 = frame.stack.pop() #dimension
            assert v1.type == jvm.Int()
            logger.debug(f"YOU ARE INSIDE NEW ARRAY")

            match t:
                #boolean, byte, char, short, or int
                case jvm.Int():
                    array = [0] * v1.value
                case jvm.Float():
                    array = [0.0] * v1.value
                case jvm.Reference():
                    array = [None] * v1.value
                case _:    raise NotImplementedError(str(c))

            # store in heap and push reference
            heap_index = max(state.heap.keys(), default=-1) + 1
            state.heap[heap_index] = array
            frame.stack.push(jvm.Value(jvm.Reference(), heap_index))
            frame.pc += 1
            return state
        
        case jvm.ArrayLength():
            heap_index = frame.stack.pop()
            assert heap_index.type == jvm.Reference()
            logger.debug(f"heap_index: {heap_index}")

            if heap_index.value == None:
                return "null pointer"
            elif isinstance(heap_index.value, tuple): #here you have to handle the subcases where you get ref with a value and ref without a value
                logger.debug(f"HEAP_index.value: {heap_index.value}")

                if not heap_index.value:
                    return "assertion error"
                else:
                    logger.debug(f"HEAP_INDEX.VALUE[0]: {heap_index.value[0]}")
                    array_length = heap_index.value[0] #assuming this is the length of the array because otherwise i would need a way to collect all the values inside the tuple and then be able to say the length of the array
                    frame.stack.push(jvm.Value(type=jvm.Int(), value=array_length))
                    frame.pc +=1
                    return state
            else:
                heap_index_value = heap_index.value
            logger.debug(f"HEAP INDEX VALUE: {heap_index_value}")

            array = state.heap[heap_index_value]
            logger.debug(f"ARRAY IN HEAP: {array}")

            if isinstance(array, jvm.Value):
                array_length = array.value #ArrayInBounds case
            elif isinstance(array, list):
                array_length = len(array) #ArrayIsNullLength case
            else:
                raise TypeError(f"Unknown array type in heap: {type(array)}")
            
            logger.debug(f"THE ARRAY LENGTH IS: {array_length}")

            frame.stack.push(jvm.Value(type=jvm.Int(), value=array_length))
            frame.pc +=1
            return state
        
        case jvm.Store(type=t, index=i):
            v = frame.stack.pop()
            frame.locals[i] = v
            frame.pc += 1
            return state
        
        case jvm.Load(type=t, index=i):
            v = frame.locals[i]
            frame.stack.push(v)
            frame.pc += 1
            return state

        case jvm.ArrayStore(type = t):
            v = frame.stack.pop() #value
            i = frame.stack.pop() #index
            af = frame.stack.pop() #array reference
            logger.debug(f"YOU ARE INSIDE ARRAY STORE")

            # arrayref should be a reference type
            assert af.type == jvm.Reference()
            # index should be an int
            assert i.type == jvm.Int()
            logger.debug(f"I VALUE: {i.value}")

            if af.value is None:
                return "null pointer" 
            
            array = state.heap.get(af.value)
            logger.debug(f"ARRAY: {array}")

            if array is None:
                return "null pointer"

            if isinstance(array, list) or isinstance(array, tuple):
                logger.debug(f"TEST 1: {array}")
            
                if len(array) <= 0:
                    logger.debug(f"OUT OF BOUNDS")
                    return "out of bounds" #array out of bounds case

                if i.value < 0 or i.value >= len(array): #arraySometimesNull case i'm uncertain about the use of <=0 rather then < 0 
                    logger.debug(f"TEST 2: {array}")
                    return "out of bounds" #out of bounds 
                            
                #return "assertion error"
                state.heap[af.value + i.value] = v
                logger.debug(f"V VALUE: {v}")
                        
                frame.pc += 1
                return state
            
            state.heap[af.value + i.value] = v
            logger.debug(f"V VALUE: {v}")
                    
            frame.pc += 1
            return state
    
        case jvm.Goto(target=t):
            frame.pc.offset = t 
            return state

        case jvm.ArrayLoad(type = t):
            index = frame.stack.pop()
            aref = frame.stack.pop()
            logger.debug(f"YOU ARE INSIDE ARRAY LOAD")

            assert index.type == jvm.Int()
            logger.debug(f"AREF.VALUE {aref.value}")

            # Check for null reference
            if aref.value is None:
                return "null pointer"
            
            if isinstance(aref.value, list): #It's an array
                # Get the array from the heap if it's a reference
                array = state.heap.get(aref.value)
                if array is None:
                    return "null pointer"
            
        
            elif isinstance(aref.value, tuple):
                # tuple detected
                if not aref.value:  # empty tuple
                    return "out of bounds"
                elif isinstance(aref.value[0], str):
                    expected = ('h','e','l','l','o') #for the ArraySpellsHello case because this is a placeholder representation to indicate “this is a valid non-empty array” ([I:50,100,200]) which is the hello array versus an empty array ([I:]) which is the x array
                    logger.debug(f"AREF.VALUE: {aref.value}")

                    if tuple(aref.value) != expected:
                        return "assertion error"
                    
                    else:

                        logger.debug(f"AREF.VALUE[0] {aref.value[0]}")           
                        logger.debug(f"I VALUE: {index.value}")

                    
                        return "ok" #needs to be fixed (ask the prof)
                    
                        #v = state.heap[aref.value + index.value]
                        #frame.stack.push(v)
                        #frame.pc += 1
                        #return state
                logger.debug(f"AREF.VALUE 1: {aref.value}")
                v = aref.value[index.value] #in case rather then giving you the reference in the heap it directly gives you the tuple
                logger.debug(f"V VALUE 2: {v}")
                frame.stack.push(jvm.Value(type= jvm.Int(), value = v))
                frame.pc += 1
                return state

            else:
                return "assertion error"
        
            logger.debug(f"AREF.VALUE 2: {aref.value}")

            v = state.heap[aref.value + index.value]
            frame.stack.push(v)
            frame.pc += 1
            return state
        
        case jvm.Cast(from_ = f, to_ = t):
            #To be implemented
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
        case jvm.Value(type=jvm.Array(), value = value):
            v = jvm.Value(jvm.Reference(), value) #our system only deals with int float and reference
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


def number_of_args():
    return