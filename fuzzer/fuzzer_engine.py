# fuzzer/fuzzer_engine.py (modified)
import itertools

from config import FuzzerConfig
from coverage_tracker import CoverageTracker
from input_generator import InputGenerator
from java_runner import JavaRunner
from corpus_manager import CorpusManager
from error_detector import ErrorDetector

class FuzzerEngine:
    def __init__(self, config: FuzzerConfig):
        self.config = config
        # Initialize the Java program caller (to interface with the instrumented Java program)
        self.java_runner = JavaRunner(
            java_class_path=config.java_class_path,
            target_method=config.target_method,
            config=self.config # Pass the config object to JavaRunner
        )
        # Initialize other core components
        self.coverage_tracker = CoverageTracker(config=self.config)
        # --- Modification: Let InputGenerator know the number of parameters ---
        num_params = len(config.guided_seeds) if config.guided_seeds else 1

        self.input_generator = InputGenerator(input_type=int, num_params=num_params)
        self.corpus_manager = CorpusManager()
        self.error_detector = ErrorDetector()

    def initialize(self):
        """Initializes: loads guided seeds and random seeds, and returns this initial set."""
        initial_corpus = []

        # --- Core modification: Load guided seeds ---
        if self.config.guided_seeds:
            # Use itertools.product to calculate the Cartesian product of all parameter combinations
            # Example: [[1,2], [10]] -> [(1, 10), (2, 10)]
            guided_seeds_product = list(itertools.product(*self.config.guided_seeds))
            print(f"Loading {len(guided_seeds_product)} guided seeds from static analysis.")
            initial_corpus.extend(guided_seeds_product)

        # Add some random seeds to increase diversity
        random_seeds = self.input_generator.generate_seeds(self.config.seed_count)
        print(f"Additionally generating {len(random_seeds)} random seeds.")
        # initial_corpus.extend(random_seeds)

        for seed in random_seeds:
            self.corpus_manager.add(seed)

        print(f"Initialization complete, corpus size: {self.corpus_manager.size()}")
        print(f"Java target method: {self.config.target_method}")
        print(f"Java classpath: {self.config.java_class_path}")

        # Return a clear set of initial seeds
        return initial_corpus

    def run(self):
        """Starts the fuzzing test (core scheduling logic)"""
        # Receive the list of initial seeds explicitly returned by initialize
        initial_seeds_to_test = self.initialize()

        # First, execute all seeds in the initial corpus once
        print("Testing the initial corpus...")
        for seed in initial_seeds_to_test:
            self.coverage_tracker.track_execution(self.java_runner, seed)
        print("Initial corpus testing complete.")

        iteration = 0
        while iteration < self.config.max_iterations and self.corpus_manager.size() > 0:
            iteration += 1
            # 1. Randomly select a valid input from the corpus
            original_input = self.corpus_manager.get_random_input()

            # 2. Mutate the input (generate multiple mutants)
            for _ in range(self.config.mutate_count):
                new_input = self.input_generator.mutate(original_input)

                # 3. Execute the Java program, track coverage and exceptions
                has_new_coverage, error_msg = self.coverage_tracker.track_execution(
                    self.java_runner, new_input
                )

                # 4. Detect and record errors
                if error_msg:
                    self.error_detector.detect(new_input, error_msg)

                # 5. If there is new coverage, add the input to the corpus
                if has_new_coverage:
                    self.corpus_manager.add(new_input)

            # Print progress (every 1000 iterations)
            if iteration % 1000 == 0:
                coverage_stats = self.coverage_tracker.get_coverage_stats2()
                print(
                    f"Iteration {iteration:5d} | "
                    f"Corpus size {self.corpus_manager.size():4d} | "
                    f"Covered branches {coverage_stats['total_covered_branches']:4d} | "
                    f"Errors {self.error_detector.error_count()}"
                )
        # Output test summary
        self._print_summary()

    def _print_summary(self):
        coverage_stats = self.coverage_tracker.get_coverage_stats2()
        print("\n" + "="*50)
        print("Fuzzing finished")
        print("="*50)
        print(f"Total iterations: {self.config.max_iterations}")
        print(f"Number of valid test cases: {self.corpus_manager.size()}")
        print(f"Total number of covered branches: {coverage_stats['total_covered_branches']}")
        print(f"Number of detected errors: {self.error_detector.error_count()}")
        if self.error_detector.get_errors():
            print("\nError details:")
            for i, error in enumerate(self.error_detector.get_errors(), 1):
                print(f"\n{i}. Input: {error['input']}")
                print(f"   Error type: {error['error_type']}")
                print(f"   Error message: {error['error_message'][:1000]}...")  # Truncate to the first 1000 characters