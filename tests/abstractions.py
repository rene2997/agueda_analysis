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

  z = Sign.binary_add(s, d)
  print(f"Result: {z}")
  assert z.values.issubset({'+', '-', '0'})

test_sign_add_abstraction()