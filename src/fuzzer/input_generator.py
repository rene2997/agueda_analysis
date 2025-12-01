# fuzzer/input_generator.py
import random
from typing import List, Any

class InputGenerator:
    def __init__(self, input_type: type = int, num_params: int = 1):
        """
        Initializes the input generator
        :param input_type: The target input type (default is int, to match division_loop(int n) in the proposal)
        """
        self.input_type = input_type
        self.num_params = num_params

        self.random = random.Random()
        self.random.seed(42)  # Fixed seed to ensure reproducibility

    def generate_seeds(self, count: int = 100) -> List[Any]:
        """
        Generates initial seed inputs (covering common and boundary values)
        :param count: The number of seeds
        :return: A list of seeds
        """
        seeds = []
        for _ in range(count):
            # Generate a random integer for each parameter and form a tuple
            seed = tuple(random.randint(-100, 100) for _ in range(self.num_params))
            seeds.append(seed)
        return seeds

    def mutate(self, original_input):
        """Mutates a random element in the input tuple"""
        if not isinstance(original_input, tuple):
            # Compatible with old single integer input
            original_input = (original_input,)

        mutated_list = list(original_input)
        if not mutated_list:
            return ()

        # Randomly select a parameter to mutate
        idx_to_mutate = random.randrange(len(mutated_list))

        # Simple mutation strategy: randomly add/subtract a value
        mutation_value = random.randint(-10, 10)
        mutated_list[idx_to_mutate] += mutation_value

        return tuple(mutated_list)

    # def mutate(self, original_input: Any) -> Any:
    #     """
    #     Mutates the input (core: generates new inputs based on valid inputs to trigger new paths)
    #     Mutation strategy: for int type, use arithmetic mutations such as "random bit flip, add/subtract offset, multiply/divide by 2" (suitable for loop/arithmetic-intensive code)
    #     :param original_input: The original valid input
    #     :return: The mutated new input
    #     """
    #     if self.input_type == int:
    #         mutation_choice = self.random.choice([
    #             self._bit_flip,    # Randomly flip 1 bit
    #             self._add_offset,  # Add/subtract a random offset
    #             self._multiply_divide,  # Multiply/divide by 2 (to match the n /= 2 loop in the proposal)
    #             self._negate       # Negate
    #         ])
    #         return mutation_choice(original_input)
    #     return original_input

    # The following are specific mutation strategies
    def _bit_flip(self, x: int) -> int:
        """Randomly flips 1 bit of x"""
        bit_pos = self.random.randint(0, 30)  # For 32-bit int, to avoid sign bit overflow
        return x ^ (1 << bit_pos)

    def _add_offset(self, x: int) -> int:
        """Adds/subtracts a random offset (-10~10)"""
        offset = self.random.randint(-10, 10)
        return x + offset

    def _multiply_divide(self, x: int) -> int:
        """Multiplies or divides by 2 (avoids division by zero)"""
        if x == 0:
            return x * 2
        return x * 2 if self.random.choice([True, False]) else x // 2

    def _negate(self, x: int) -> int:
        """Negates the number"""
        return -x