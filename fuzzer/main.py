import argparse
from config import FuzzerConfig
from fuzzer_engine import FuzzerEngine

def main():
    parser = argparse.ArgumentParser(description="Java Coverage-Based Fuzzer (interfacing with ASM instrumentation)")
    # Java-related parameters (can be specified via command line)
    parser.add_argument("--java-class-path", default="bin:lib/asm.jar", help="Java class path")
    parser.add_argument("--target-class", default="com.test.DivisionLoop", help="Target Java class name (including package name)")
    # Fuzzing parameters
    parser.add_argument("--max-iter", type=int, default=10000, help="Maximum number of iterations")
    parser.add_argument("--seed-count", type=int, default=100, help="Initial number of seeds")

    # Bitmap
    parser.add_argument("--coverage-map-size", type=int, default=65536, help="Size of the coverage bitmap")
    args = parser.parse_args()

    # Initialize configuration
    config = FuzzerConfig(
        java_class_path=args.java_class_path,
        target_class=args.target_class,
        max_iterations=args.max_iter,
        seed_count=args.seed_count,
        coverage_map_size=args.coverage_map_size
    )

    # Start fuzzer
    fuzzer = FuzzerEngine(config)
    # fuzzer.run()
    fuzzer.run2()

if __name__ == "__main__":
    main()