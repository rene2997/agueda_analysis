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
        if initial_seeds_to_test:
            print("Testing the initial corpus...")
            for seed in initial_seeds_to_test:
                has_new_coverage, is_crash, error_msg = self.coverage_tracker.track_execution(self.java_runner, seed)
                if is_crash:
                    # This is an important discovery! Record it.
                    # Error details have been printed in coverage_tracker, here we only record the event itself.
                    self.error_detector.detect(seed, error_msg)

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
                has_new_coverage, is_crash, error_msg = self.coverage_tracker.track_execution(
                    self.java_runner, new_input
                )

                # 4. Detect and record errors, using the is_crash signal
                if is_crash:
                    # This is an important discovery! Record it.
                    # Error details have been printed in coverage_tracker, here we only record the event itself.
                    self.error_detector.detect(new_input, error_msg)

                # 5. If this input discovers new coverage, it is valuable.
                if has_new_coverage:
                    self.corpus_manager.add(new_input)

            # Print progress (every 1000 iterations)
            if iteration % 1000 == 0:
                coverage_stats = self.coverage_tracker.get_coverage_stats()
                print(
                    f"Iteration {iteration:5d} | "
                    f"Corpus size {self.corpus_manager.size():4d} | "
                    f"Covered branches {coverage_stats['total_covered_branches']:4d} | "
                    f"Errors {self.error_detector.error_count()}"
                )
        return self.get_summary() # Return the summary

    def get_summary(self) -> dict:
        """
        Gathers the final results of the fuzzing session.

        Returns:
            A dictionary containing final statistics and crash details.
        """
        coverage_stats = self.coverage_tracker.get_coverage_stats()
        crashes = self.error_detector.get_errors()

        summary = {
            "total_iterations": self.config.max_iterations,
            "corpus_size": self.corpus_manager.size(),
            "total_covered_branches": coverage_stats['total_covered_branches'],
            "crash_count": len(crashes),
            "crashes": crashes
        }

        # Also print the summary for interactive use
        print("\n" + "=" * 50)
        print("Fuzzing finished")
        print("=" * 50)
        print(f"Total iterations: {summary['total_iterations']}")
        print(f"Number of valid test cases: {summary['corpus_size']}")
        print(f"Total number of covered branches: {summary['total_covered_branches']}")
        print(f"Number of detected errors: {summary['crash_count']}")
        if summary['crashes']:
            print("\nError details:")
            for i, error in enumerate(summary['crashes'], 1):
                print(f"\n{i}. Input: {error['input']}")
                print(f"   Error message: {error['error_message']}")

        return summary
