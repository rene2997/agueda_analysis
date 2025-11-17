from hypothesis import given, strategies
from hypothesis.strategies import integers, sets
from src.static_analysis.abstractions import Sign, AState, PC, PerVarFrame, Stack

@given(sets(integers()))
def test_valid_abstraction_list(xs):
  s = Sign.abstract(xs) 
  assert(s == '+' or '-' or '0')
#test_valid_abstraction_list()

@given(sets(integers()), sets(integers()))
def test_sign_add_abstraction(xs, xd):
  s = Sign.abstract(xs)
  d = Sign.abstract(xd) 
  print(s, d)
  z = Sign.binary_op(s, d, Sign.sign_add)
  print(f"Result: {z}")
  assert z.values.issubset({'+', '-', '0'})
#test_sign_add_abstraction()

@given(sets(integers()), sets(integers()))
def test_sign_sub_abstraction(xs, xd):
  s = Sign.abstract(xs)
  d = Sign.abstract(xd) 
  print(s, d)
  z = Sign.binary_op(s, d, Sign.sign_sub)
  print(f"Result: {z}")
  assert z.values.issubset({'+', '-', '0'})
#test_sign_sub_abstraction()

@given(sets(integers()), sets(integers()))
def test_sign_mul_abstraction(xs, xd):
  s = Sign.abstract(xs)
  d = Sign.abstract(xd) 
  print(s, d)
  z = Sign.binary_op(s, d, Sign.sign_mul)
  print(f"Result: {z}")
  assert z.values.issubset({'+', '-', '0'})
#test_sign_mul_abstraction()

@given(sets(integers()), sets(integers()))
def test_sign_div_abstraction(xs, xd):
  s = Sign.abstract(xs)
  d = Sign.abstract(xd) 
  print(s, d)
  z = Sign.binary_op(s, d, Sign.sign_div)
  print(f"Result: {z}")
  assert z.values.issubset({'+', '-', '0'})
#test_sign_div_abstraction() #remember that if in the set there's a d this means that 

# ----- Sign -----

sign_atom = strategies.sampled_from(["+", "-", "0"])
sign_set = strategies.sets(sign_atom, max_size=3)
sign_strategy = sign_set.map(lambda s: Sign(s))


# ----- PC -----

# Minimal dummy AbsMethodID type
class DummyMethod:
    pass

pc_strategy = strategies.builds(
    PC,
    method=strategies.just(DummyMethod()),
    offset=strategies.integers()
)


# ----- Stack[T] -----

def stack_strategy(inner_strategy):
    return strategies.builds(Stack, items=strategies.lists(inner_strategy))


# ----- PerVarFrame -----

frame_strategy = strategies.builds(
    PerVarFrame,
    locals=strategies.dictionaries(strategies.integers(), sign_strategy),
    stack=stack_strategy(sign_strategy),
    pc=pc_strategy
)


# ----- AState -----

astate_strategy = strategies.builds(
    AState,
    heap=strategies.dictionaries(strategies.integers(), sign_strategy),
    frames=stack_strategy(frame_strategy)
)

@given(astate_strategy, astate_strategy)
def test_valid_AState_join_list(a,b):
  #print(f"a:{a}, b:{b}\n")
  s = a.join(b)
  print(f"{s}")
test_valid_AState_join_list()