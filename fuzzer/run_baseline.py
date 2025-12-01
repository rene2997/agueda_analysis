import os
import re
import json
from config import FuzzerConfig
from fuzzer_engine import FuzzerEngine

# --- Configuration ---
CASES_FILE_PATH = "../jpamb/stats/cases.txt"
RESULTS_FILE_PATH = "baseline_results.json"
DEFAULT_JAVA_CLASS_PATH = "../jpamb_customized/target/classes"
DEFAULT_AGENT_PATH = "./bytescribe-agent-1.0-SNAPSHOT.jar"
FUZZ_ITERATIONS = 10

def parse_cases(file_path):
    """
    Parses the cases.txt file to get a unique list of method signatures
    that only have one or more integer (I) parameters.
    """
    if not os.path.exists(file_path):
        print(f"Error: Cases file not found at '{file_path}'")
        return []
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    signatures = set()
    for line in lines:
        if not line.strip():
            continue
        
        signature = line.strip().split()[0]
        
        # Extract parameters part
        match = re.search(r'\((.*?)\)', signature)
        if not match:
            continue
        
        params_str = match.group(1)
        
        # Check if params_str is NOT empty and contains only 'I'
        if params_str and all(c == 'I' for c in params_str):
            signatures.add(signature)
            
    return sorted(list(signatures))

def count_params(method_signature):
    """Counts the number of parameters from a Java method signature."""
    # Regex to find the content within the parentheses
    match = re.search(r'\((.*?)\)', method_signature)
    if not match:
        return 0
    
    params_str = match.group(1)
    return len(params_str)


def run_fuzzer_for_method(method_signature, num_params):
    """Configures and runs the fuzzer for a single method."""
    print("\n" + "="*60)
    print(f"Testing method: {method_signature}")
    print(f"Detected {num_params} integer parameters.")
    print("="*60)

    config = FuzzerConfig(
        java_class_path=DEFAULT_JAVA_CLASS_PATH,
        target_method=method_signature,
        guided_seeds=[],  # No guided seeds for baseline
        agent_path=DEFAULT_AGENT_PATH,
        max_iterations=FUZZ_ITERATIONS,
        seed_count=100,
        coverage_map_size=65536
    )
    
    # Override the number of parameters for the input generator
    engine = FuzzerEngine(config)
    engine.input_generator.num_params = num_params

    summary = engine.run()
    return summary


def main():
    """Main script execution."""
    method_signatures = parse_cases(CASES_FILE_PATH)
    if not method_signatures:
        print("No suitable methods with only integer parameters found for baseline testing.")
        return

    print(f"Found {len(method_signatures)} methods with only integer parameters.")
    all_results = {}

    for signature in method_signatures:
        num_params = count_params(signature)
        result = run_fuzzer_for_method(signature, num_params)
        all_results[signature] = result

    # Save results to a file
    with open(RESULTS_FILE_PATH, 'w') as f:
        json.dump(all_results, f, indent=4)

    print(f"\nBaseline testing complete. Results saved to '{RESULTS_FILE_PATH}'")
    
    # Final summary
    print("\n" + "="*60)
    print("Baseline Fuzzing Summary (Integer-Only Param Methods)")
    print("="*60)
    for method, result in all_results.items():
        status = "PASSED" if result['crash_count'] == 0 else f"FAILED ({result['crash_count']} crashes)"
        print(f"- {method:<60} {status}")


if __name__ == "__main__":
    main()