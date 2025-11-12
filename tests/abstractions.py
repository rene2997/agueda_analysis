from hypothesis import given
from hypothesis.strategies import integers, sets
from src.static_analysis.abstractions import Sign

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
test_sign_div_abstraction() #remember that if in the set there's a d this means that 