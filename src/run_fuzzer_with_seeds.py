import json
from pathlib import Path

from fuzzer.fuzzer_api import start_fuzzing

# Resolve important paths relative to this file
BASE_DIR = Path(__file__).resolve().parent          # .../agueda_analysis/src
ROOT_DIR = BASE_DIR.parent                          # .../agueda_analysis

guided_payload = {
    "method": "jpamb.cases.Tricky.collatz:(I)V",
    "guided_seeds": [[0]],
}

# Where jpamb compiled classes live
java_cp = str(ROOT_DIR / "jpamb" / "target" / "classes")

# Absolute path to the agent JAR
agent_path = str(BASE_DIR / "fuzzer" / "bytescribe-agent-1.0-SNAPSHOT.jar")

print(f"[DEBUG] Using java_cp={java_cp}")
print(f"[DEBUG] Using agent_path={agent_path}")

results = start_fuzzing(
    target_method=guided_payload["method"],
    guided_seeds=guided_payload["guided_seeds"],
    java_class_path=java_cp,
    agent_path=agent_path,
    max_iterations=100,
    seed_count=20,
    coverage_map_size=65536,
)

print("FUZZER_RESULTS:", json.dumps(results, indent=2))