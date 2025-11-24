# fuzzer/fuzzer_engine.py (modified)
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
            target_class=config.target_class,
            config=self.config # Pass the config object to JavaRunner
        )
        # Initialize other core components
        self.coverage_tracker = CoverageTracker(config=self.config)
        self.input_generator = InputGenerator(input_type=int)
        self.corpus_manager = CorpusManager()
        self.error_detector = ErrorDetector()

    def initialize(self):
        """Initialize: generate initial seeds and add them to the corpus"""
        seeds = self.input_generator.generate_seeds(self.config.seed_count)
        for seed in seeds:
            self.corpus_manager.add(seed)
        print(f"Initialization complete: {len(seeds)} initial seeds generated")
        print(f"Java target class: {self.config.target_class}")
        print(f"Java class path: {self.config.java_class_path}")

    def run(self):
        """Start fuzzing (core scheduling logic)"""
        self.initialize()
        iteration = 0
        while iteration < self.config.max_iterations and self.corpus_manager.size() > 0:
            iteration += 1
            # 1. Randomly select a valid input from the corpus
            original_input = self.corpus_manager.get_random_input()
            # 2. Mutate the input (generate multiple variants)
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
                coverage_stats = self.coverage_tracker.get_coverage_stats()
                print(
                    f"Iteration {iteration:5d} | "
                    f"Corpus size {self.corpus_manager.size():4d} | "
                    f"Covered branches {coverage_stats['total_covered_branches']:4d} | "
                    f"Errors {self.error_detector.error_count()}"
                )
        # Print test summary
        self._print_summary()

    def run2(self):
        """Start fuzzing (core scheduling logic)"""
        self.initialize()
        iteration = 0
        while iteration < self.config.max_iterations and self.corpus_manager.size() > 0:
            iteration += 1
            # 1. Randomly select a valid input from the corpus
            original_input = self.corpus_manager.get_random_input()

            # 2. Mutate the input (generate multiple variants)
            for _ in range(self.config.mutate_count):
                new_input = self.input_generator.mutate(original_input)

                # 3. Execute the Java program, track coverage and exceptions
                has_new_coverage, error_msg = self.coverage_tracker.track_execution2(
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
        # Print test summary
        self._print_summary2()

    def _print_summary(self):
        coverage_stats = self.coverage_tracker.get_coverage_stats()
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
                print(f"   Error message: {error['error_message'][:100]}...")  # Truncate to the first 100 characters

    def _print_summary2(self):
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