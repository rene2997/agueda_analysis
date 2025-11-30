from config import FuzzerConfig
from fuzzer_engine import FuzzerEngine


def start_fuzzing(
        target_method: str,
        guided_seeds: list[list[int]],
        java_class_path: str,
        agent_path: str,
        max_iterations: int = 10000,
        seed_count: int = 100,
        coverage_map_size: int = 65536
) -> dict:
    """
    Programmatic entry point for the fuzzer.

    This function initializes and runs the entire fuzzing process with the
    provided configuration and returns the results.

    Args:
        target_method: The full signature of the Java method to fuzz.
        guided_seeds: A list of lists containing seed values from static analysis.
        java_class_path: The classpath for the target Java project.
        agent_path: The path to the instrumentation agent JAR.
        max_iterations: The maximum number of fuzzing iterations.
        seed_count: The number of additional random seeds to generate.
        coverage_map_size: The size of the coverage bitmap.
        map_output_path: The path for the coverage map file.

    Returns:
        A dictionary containing the fuzzing results, including coverage
        statistics and any crashes found.
    """
    print("--- Fuzzer API called ---")

    # 1. Create the configuration object from function arguments
    config = FuzzerConfig(
        java_class_path=java_class_path,
        target_method=target_method,
        guided_seeds=guided_seeds,
        max_iterations=max_iterations,
        seed_count=seed_count,
        agent_path=agent_path,
        coverage_map_size=coverage_map_size
    )

    # 2. Initialize the fuzzer engine
    fuzzer = FuzzerEngine(config)

    # 3. Run the fuzzer
    fuzzer.run()

    # 4. Get and return the results
    results = fuzzer.get_summary()
    print("--- Fuzzer API finished ---")
    return results
