from .config import FuzzerConfig
from .fuzzer_engine import FuzzerEngine


def start_fuzzing(
        target_method: str,
        guided_seeds: list[list[int]],
        java_class_path: str,
        agent_path: str,
        max_iterations: int = 10000,
        seed_count: int = 100,
        coverage_map_size: int = 65536,
        print_summary: bool = False,   # <--- NEW
) -> dict:
    ...
    print("--- Fuzzer API called ---")
    config = FuzzerConfig(
        java_class_path=java_class_path,
        target_method=target_method,
        guided_seeds=guided_seeds,
        max_iterations=max_iterations,
        seed_count=seed_count,
        agent_path=agent_path,
        coverage_map_size=coverage_map_size
    )

    fuzzer = FuzzerEngine(config)
    fuzzer.run()

    # pass flag through
    results = fuzzer.get_summary(print_summary=print_summary)

    print("--- Fuzzer API finished ---")
    return results