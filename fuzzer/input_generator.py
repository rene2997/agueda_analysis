# fuzzer/input_generator.py
import random
from typing import List, Any

class InputGenerator:
    def __init__(self, input_type: type = int):
        """
        Initialize the input generator
        :param input_type: Target input type (default is int, to match division_loop(int n) in the proposal)
        """
        self.input_type = input_type
        self.random = random.Random()
        self.random.seed(42)  # Fixed seed to ensure reproducibility

    def generate_seeds(self, count: int = 100) -> List[Any]:
        """
        Generate initial seed inputs (covering common and boundary values)
        :param count: Number of seeds
        :return: List of seeds
        """
        seeds = []
        if self.input_type == int:
            # Include boundary values (0, max, min, powers of 2, to match the 1024=2^10 scenario in the proposal)
            boundary_values = [0, 1, -1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048,
                               int(1e5), int(-1e5), int(2**31-1), int(-2**31)]
            seeds.extend(boundary_values)
            # Supplement with random int values to ensure seed diversity
            while len(seeds) < count:
                seeds.append(self.random.randint(-10**6, 10**6))
        # Can be extended to other types later (e.g., str: generate random strings, common keywords)
        return list(set(seeds))  # Deduplicate

    def mutate(self, original_input: Any) -> Any:
        """
        Mutate the input (core: generate new inputs based on valid inputs to trigger new paths)
        Mutation strategy: For int type, use arithmetic mutations such as "randomly modify bits, add/subtract offset, multiply/divide by 2" (suitable for loop/arithmetic-intensive code)
        :param original_input: Original valid input
        :return: Mutated new input
        """
        if self.input_type == int:
            mutation_choice = self.random.choice([
                self._bit_flip,    # Randomly flip 1 binary bit
                self._add_offset,  # Add/subtract random offset
                self._multiply_divide,  # Multiply/divide by 2 (to match the n /= 2 loop in the proposal)
                self._negate       # Negate
            ])
            return mutation_choice(original_input)
        return original_input

    # The following are specific mutation strategies
    def _bit_flip(self, x: int) -> int:
        """Randomly flip 1 binary bit of x"""
        bit_pos = self.random.randint(0, 30)  # For 32-bit int, to avoid sign bit overflow
        return x ^ (1 << bit_pos)

    def _add_offset(self, x: int) -> int:
        """Add/subtract a random offset (-10~10)"""
        offset = self.random.randint(-10, 10)
        return x + offset

    def _multiply_divide(self, x: int) -> int:
        """Multiply by 2 or divide by 2 (avoid division by zero)"""
        if x == 0:
            return x * 2
        return x * 2 if self.random.choice([True, False]) else x // 2

    def _negate(self, x: int) -> int:
        """Negate"""
        return -x