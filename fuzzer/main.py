import argparse
import json

from config import FuzzerConfig
from fuzzer_engine import FuzzerEngine

def main():
    parser = argparse.ArgumentParser(description="Java Coverage-Guided Fuzzer with Static Analysis Seeds")

    # --- Main change: Use a JSON file as input ---
    parser.add_argument("--input-json", default="./guided_fuzz_config.json", help="Path to the JSON configuration file containing the target method and guided seeds")

    # Java-related parameters (can be specified via command line)
    parser.add_argument("--java-class-path", default="./jpamb/target/classes", help="Java classpath")
    parser.add_argument("--target-method", default="jpamb.cases.Simple.divideByN:(I)I", help="Target Java method for testing (with package name, class name, and input/output parameter types)")
    parser.add_argument("--agent-path", default="./bytescribe-agent-1.0-SNAPSHOT.jar", help="Path to the instrumentation Agent jar package")

    # Fuzz parameters
    parser.add_argument("--max-iter", type=int, default=10000, help="Maximum number of iterations")
    parser.add_argument("--seed-count", type=int, default=100, help="Initial number of seeds")

    # Bitmap
    parser.add_argument("--coverage-map-size", type=int, default=65536, help="Size of the coverage bitmap")
    args = parser.parse_args()

    # --- New: Read and parse the JSON file ---
    try:
        with open(args.input_json, 'r') as f:
            fuzz_config_data = json.load(f)
        target_method = fuzz_config_data["method"]
        guided_seeds = fuzz_config_data["guided_seeds"]
    except (FileNotFoundError, KeyError) as e:
        print(f"Error: Could not read or parse '{args.input_json}'. Please ensure the file exists and is correctly formatted.")
        print(f"Specific error: {e}")
        return

    # Initialize configuration
    config = FuzzerConfig(
        java_class_path=args.java_class_path,
        target_method=target_method,
        guided_seeds = guided_seeds,
        agent_path=args.agent_path,
        max_iterations=args.max_iter,
        seed_count=args.seed_count,
        coverage_map_size=args.coverage_map_size
    )

    # Start the fuzzer
    fuzzer = FuzzerEngine(config)
    fuzzer.run()

if __name__ == "__main__":
    main()