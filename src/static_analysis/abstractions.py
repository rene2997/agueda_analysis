from dataclasses import dataclass
from typing import List, TypeVar, Generic
from abc import ABC, abstractmethod

@dataclass
class Sign:
    values: set[str]
    @staticmethod
    def top():
        return Sign({"+", "-", "0"})
 
    def __le__(self, other) -> bool:
        return self.values <= other.values
 
    def __or__(self, other) -> bool:
        return Sign(self.values | other.values)
    
    def __and__(self, other) -> bool:
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
        
    def binary_add(av1, av2):
        print(f"add: {av1=} {av2=}")
        outvalues = set()
        if(av1.values == [] or av2.values == []):
            pass
        else:
            for x in av1.values:
                for y in av2.values:
                    print(f"x:{x}")
                    print(f"y:{y}")
                    match (x, y):
                        case ("+", "+"):
                            outvalues.add("+")
                        case ("+", "-"):
                            outvalues.add("-")
                            outvalues.add("+")
                            outvalues.add("0")
                        case ("+", "0"):
                            outvalues.add("+")
                        case ("-", "+"):
                            outvalues.add("-")
                            outvalues.add("+")
                            outvalues.add("0")
                        case ("-", "-"):
                            outvalues.add("-")
                        case ("-", "0"):
                            outvalues.add("-")
                        case ("0", "+"):
                            outvalues.add("+")
                        case ("0", "-"):
                            outvalues.add("-")
                        case ("0", "0"):
                            outvalues.add("0")
            return Sign(outvalues) #Any function that uses yield becomes a generator, not a normal function.

    def binary_div(av1, av2):
        print(f"div: {av1=} {av2=}")
        outvalues = set()
        for x in av1.values:
            for y in av2.values:
                match (x, y):
                    case ("+", "+"):
                        outvalues.add("+") #otherwise we would return an empty set
                    case ("+", "-"):
                        outvalues.add("-")
                    case ("+", "0"):
                        yield "divide by zero"
                    case ("-", "+"):
                        outvalues.add("-")
                    case ("-", "-"):
                        outvalues.add("-")
                    case ("-", "0"):
                        yield "divide by zero"
                    case ("0", "+"):
                        outvalues.add("0")
                    case ("0", "-"):
                        outvalues.add("0")
                    case ("0", "0"):
                        outvalues.add("0")
        return Sign(outvalues)

    def binary_sub(av1, av2):
        print(f"div: {av1=} {av2=}")
        outvalues = set()
        for x in av1.values:
            for y in av2.values:
                match (x, y):
                    case ("+", "+"):
                        outvalues.add("-", "0", "+")
                    case ("+", "-"):
                        outvalues.add("+")
                    case ("+", "0"):
                        outvalues.add("+")
                    case ("-", "+"):
                        outvalues.add("-", "0", "+") 
                    case ("-", "-"):
                        outvalues.add("-", "0", "+") 
                    case ("-", "0"):
                        outvalues.add("+")
                    case ("0", "+"):
                        outvalues.add("-", "0") 
                    case ("0", "-"):
                        outvalues.add("0", "+") 
                    case ("0", "0"):
                        outvalues.add("0")
        return Sign(outvalues)
    
    def binary_mul(av1, av2):
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
                        outvalues.add("0")
                    case ("-", "+"):
                        outvalues.add("-")
                    case ("-", "-"):
                        outvalues.add("-")
                    case ("-", "0"):
                        outvalues.add("0")
                    case ("0", "+"):
                        outvalues.add("0")
                    case ("0", "-"):
                        outvalues.add("0")
                    case ("0", "0"):
                        outvalues.add("0")
        return Sign(outvalues)

@dataclass
class Parity:
    values: set[str]
    @staticmethod
    def top():
        return Parity({"even", "odd"})
 
    def __le__(self, other) -> bool:
        return self.values <= other.values
 
    def __or__(self, other) -> bool:
        return Parity(self.values | other.values)
    
    def __and__(self, other) -> bool:
        return Parity(self.values & other.values)
 
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

"""""
#these are all the methods inside Abstraction that are gonna be overwritten by every other method
#bottom(): impossible value (empty set of concrete values)

#top(): all possible values

#is_le(&self, other): lattice ordering (self ⊑ other)

#join(&self, other): least upper bound (union / merge)

#meet(&self, other): greatest lower bound (intersection)

#from(value): abstraction of a concrete integer

#contains(value): checks if the abstract value contains that concrete int

#from_set: helper that unions multiple concrete values into one abstract value

class Abstraction(ABC):

    @classmethod
    @abstractmethod
    def bottom(self):
        return self
    
    @classmethod
    @abstractmethod
    def top(self):
        return self
    
    @abstractmethod
    def is_le(self, other):
        return bool
    
    @abstractmethod
    def join(self, other):
        return self
    
    @abstractmethod
    def meet(self, other):
        return self
    
    @abstractmethod
    def from_value(self, value: int):
        return self
    
    @abstractmethod
    def contains(self, value: int) -> bool:
        return bool

    @classmethod
    def from_set(cls, values):
        result = cls.bottom() # calls Sign.bottom(), Interval.bottom(), etc.
        for v in values:
            result = result.join(cls.from_value(v)) # calls subclass's from_value
        return result

@dataclass
class Sign(Abstraction, Executable):
    positive : bool
    zero: bool
    negative: bool

    @staticmethod
    def bottom():
        return Sign(False, False, False)
    
    @staticmethod
    def top():
        return Sign(True, True, True)
    
    def is_le(self, other): #is less then
        return (
            self.positive <= other.positive and 
            self.zero <= other.zero and 
            self.negative <= other.negative
        )
    
    def join(self, other):
        return Sign(
            self.positive or other.positive,
            self.zero or other.zero,
            self.negative or other.negative,
        )
    
    def meet(self, other):
        return Sign(
            self.positive and other.positive,
            self.zero and other.zero,
            self.negative and other.negative,
        )
    
    @staticmethod
    def from_value(value: int):
        return Sign(
            value > 0,
            value == 0,
            value < 0,
        )
    
    def contains(self, value: int) -> bool:
        if value > 0:
            return self.positive
        if value  == 0:
            return self.zero
        return self.negative
    
    #defines how the Sign object is printed when you call it
    def __str__(self):
        parts = []
        if self.positive:
            parts.append("+")
        if self.zero:
            parts.append("0")
        if self.negative:
            parts.append("-")
        return "{" + ", ".join(parts) + "}"


@dataclass
class Parity(Abstraction, Executable):
    odd:bool
    even: bool

    @staticmethod
    def bottom():
        return Parity(False, False)

    @staticmethod
    def top():
        return Parity(True, True)
    
    def is_le(self, other):
        return self.even <= other.even and self.odd <= other.odd
    
    def join(self, other):
        return Parity(
            self.even or other.even,
            self.odd or other.odd
        )
    
    def meet(self, other):
        return Parity(
            self.even and other.even,
            self.odd and other.odd
        )
    
    @staticmethod
    def from_value(value: int):
        return Parity(
            odd = value % 2 != 0,
            even = value % 2 == 0,
        )
    
    def contains(self, value:int) -> bool:
        if value % 2 == 0:
            return self.even
        else:
            self.odd  

    def __str__(self):
        parts = []
        if self.even: parts.append("even")
        if self.odd:  parts.append("odd")
        return "{" + ", ".join(parts) + "}"
  

@dataclass
class Interval(Abstraction, Executable):
    start: int
    end: int

    @staticmethod
    def bottom():
        return Interval(
            start = 2**31 - 1,
            end = -2**31
        )
    
    @staticmethod
    def top():
        return Interval(
            start = -2**31,
            end = 2**31 - 1
        )
    
    def is_le(self, other):
        return self.start >= other.start and self.end <= other.end

    def join(self, other):
        return Interval(
            min(self.start, other.start),
            max(self.end, other.end),
        )
    
    def meet(self, other):
        return Interval(
            max(self.start, other.start),
            min(self.end, other.end),
        )
    
    @staticmethod
    def from_value(value: int):
        return Interval(value, value)
    
    def contains(self, value) -> bool:
        if  value >= self.start and value <= self.end :
            return True
        else:
            return False
        
    def __str__(self):
        start = "-∞" if self.start == -2**31 else str(self.start)
        end   = "∞"  if self.end   ==  2**31-1 else str(self.end)
        return f"({start}..{end})"
    
@dataclass
class All(Abstraction, Executable):
    sign: Sign
    interval: Interval
    parity: Parity

    @staticmethod
    def bottom():
        return All(
            Sign.bottom(),
            Interval.bottom(),
            Parity.bottom(),
        )
    
    @staticmethod
    def top():
        return All(
            Sign.top(),
            Interval.bottom(),
            Parity.bottom()
        )
    
    def is_le(self, other):
        return(
            self.sign.is_le(other.sign) and self.interval.is_le(other.interval) and self.parity.is_le(other.parity)
        )
    
    def join(self, other):
        return All(
            self.sign.join(other.sign),
            self.interval.join(other.interval),
            self.parity.join(other.parity),
        )

    def meet(self, other):
        return All(
            self.sign.meet(other.sign),
            self.interval.meet(other.interval),
            self.parity.meet(other.parity),
        )

    @staticmethod
    def from_value(value: int):
        return All(
            Sign.from_value(value),
            Interval.from_value(value),
            Parity.from_value(value),
        )

    def contains(self, value: int):
        return (
            self.sign.contains(value) and
            self.interval.contains(value) and
            self.parity.contains(value)
        )

    def __str__(self):
        return f"<{self.sign}, {self.interval}, {self.parity}>"

T = TypeVar("T", bound=Abstraction)

@dataclass
class State(Generic[T], Abstraction):
    stack: List[T]
    locals: List[T]

    # ---------- Abstraction trait ----------
    @classmethod
    def bottom(cls):
        return cls(stack=[], locals=[])

    @classmethod
    def top(cls):
        raise NotImplementedError("State<T> does not implement top()")

    def is_le(self, other):
        if len(self.stack) > len(other.stack):
            return False

        # compare stack from top to bottom
        stack_ok = all(
            a.is_le(b)
            for a, b in zip(reversed(self.stack), reversed(other.stack))
        )

        locals_ok = all(
            a.is_le(b)
            for a, b in zip(self.locals, other.locals)
        )

        return stack_ok and locals_ok

    def join(self, other):
        n = max(len(self.stack), len(other.stack))
        m = max(len(self.locals), len(other.locals))

        # stack (from top, reverse iterators)
        new_stack = []
        for a, b in zip(
            reversed(self.stack + [self.stack[0].bottom()] * n),
            reversed(other.stack + [other.stack[0].bottom()] * n),
        ):
            new_stack.append(a.join(b))

        new_stack.reverse()

        # locals
        new_locals = []
        for a, b in zip(
            self.locals + [self.locals[0].bottom()] * m,
            other.locals + [other.locals[0].bottom()] * m,
        ):
            new_locals.append(a.join(b))

        return State(new_stack, new_locals)

    def meet(self, other):
        m = max(len(self.locals), len(other.locals))

        new_stack = [a.meet(b) for a, b in zip(self.stack, other.stack)]
        new_locals = [
            a.meet(b)
            for a, b in zip(
                self.locals + [self.locals[0].bottom()] * m,
                other.locals + [other.locals[0].bottom()] * m,
            )
        ]

        return State(new_stack, new_locals)

    @classmethod
    def from_value(cls, value: int):
        raise NotImplementedError("State<T> has no from_value")

    def contains(self, value: int):
        raise NotImplementedError("State<T> has no contains")

    # ---------- JVM-like helpers ----------
    @classmethod
    def new(cls, args: List[T], n_locals: int):
        Equivalent to Rust State::new.
        padded = args + [args[0].bottom()] * (n_locals - len(args))
        return cls(stack=[], locals=padded)

    def push(self, value: T):
        self.stack.append(value)
        return self

    def pop(self):
        return self.stack.pop()

    def local(self, idx: int):
        return self.locals[idx]

    def binary_op(self, op):
        b = self.stack.pop()
        a = self.stack.pop()
        self.stack.append(op(a, b))
        return self

    def __str__(self):
        s_stack = ", ".join(str(v) for v in self.stack)
        s_locals = ", ".join(str(v) for v in self.locals)
        return f"Stack: [{s_stack}], Locals: [{s_locals}]"
"""