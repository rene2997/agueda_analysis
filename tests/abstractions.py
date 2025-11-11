from hypothesis import given
from hypothesis.strategies import integers, sets
from src.static_analysis.abstractions import Sign

@given(sets(integers()))
def test_valid_abstraction_list(xs):
  s = Sign.abstract(xs) 
  print(Sign.abstract(xs))
  assert(s == '+' or '-' or '0')

test_valid_abstraction_list()