import subprocess
import json
import tempfile
import os
from typing import Tuple, Optional, Dict, Sequence

VERBOSE = os.environ.get("FUZZER_VERBOSE") == "1"


def _parse_param_types_from_method(method_sig: str) -> list[str]:
    """
    Parse JVM descriptor in a method string like 'pkg.Class.method:(ZII)V'.
    Only distinguishes 'bool' vs 'int' for formatting inputs to Java.
    """
    if ":" not in method_sig:
        return []
    desc = method_sig.split(":", 1)[1]
    if "(" not in desc or ")" not in desc:
        return []
    args = desc[desc.index("(") + 1 : desc.index(")")]
    param_types: list[str] = []
    i = 0
    while i < len(args):
        ch = args[i]
        if ch == "[":
            i += 1
            continue
        if ch == "Z":
            param_types.append("bool")
        elif ch == "I":
            param_types.append("int")
        elif ch in ("B", "C", "S", "J", "F", "D"):
            param_types.append("int")
        elif ch == "L":
            while i < len(args) and args[i] != ";":
                i += 1
            param_types.append("int")
        else:
            param_types.append("int")
        i += 1
    return param_types

class JavaRunner:
    def __init__(self, java_class_path: str, target_method: str, config, coverage_output_path: str = "coverage_temp.json"):
        """
        :param java_class_path: Java classpath (e.g., "bin:lib/asm.jar", including instrumented class files)
        :param target_method: Target Java method for testing (with package name, class name, and input/output parameter types)
        :param coverage_output_path: File path for the instrumented Java program to output coverage data (as previously agreed)
        """
        self.java_class_path = java_class_path
        self.target_method = target_method
        self.config = config # Pass in the FuzzerConfig object
        self.runtime_class = "jpamb.Runtime"    # Fixed runtime class for executing the target method
        self.param_types = _parse_param_types_from_method(target_method)

        self.coverage_output_path = coverage_output_path
        # Ensure that there are no residual coverage output files
        if os.path.exists(coverage_output_path):
            os.remove(coverage_output_path)

    def run_java_program(self, input_data: str):
        """
        Executes the Java program using the instrumentation agent and returns the execution result.
        """
        # 1. Define the paths for the instrumentation agent and output files (read from the configuration)
        agent_path = self.config.agent_path
        shm_path = self.config.coverage_output_path
        map_path = self.config.map_output_path
        edge_path = self.config.edge_coverage_path

        # 2. Build the -javaagent argument string
        agent_args = (
            f"-javaagent:{agent_path}="
            f"size={self.config.coverage_map_size},"
            f"shm={os.path.abspath(shm_path)},"
            f"map={os.path.abspath(map_path)},"
            f"map.append=false,"
            f"perEdge=true,"
            f"perEdgePath={os.path.abspath(edge_path)}"
        )

        # 3. Format the input data
        # --- Core modification: Format the tuple into a Java parameter string ---
        def _fmt_val(idx: int, val):
            ptype = self.param_types[idx] if idx < len(self.param_types) else "int"
            if ptype == "bool":
                # InputParser expects literal true/false for boolean parameters
                return "true" if val not in (0, False) else "false"
            return str(val)

        if isinstance(input_data, tuple):
            formatted_vals = [_fmt_val(i, v) for i, v in enumerate(input_data)]
            param_str = ",".join(formatted_vals)
            formatted_input = f"({param_str})"
        else:
            # Compatible with single value cases, e.g., 42 -> "(42)"
            formatted_input = f"({_fmt_val(0, input_data)})"

        java_bin = os.environ.get("JAVA_BIN", "java")

        # 4. Build the complete Java execution command list
        command = [
            java_bin,
            agent_args,
            "-ea", # Enable assertions
            "-cp",
            self.java_class_path,
            self.runtime_class,
            self.target_method, # First argument: method signature
            formatted_input     # Second argument: formatted parameters required by the target method to be executed
        ]

        # 4.1 log (optional, controlled by FUZZER_VERBOSE)
        if VERBOSE:
            print(f"========executed java command is: {command}========")
            
        # 5. Execute the command
        try:
            # Before each execution, clear the old edge coverage file to ensure that only the current execution is counted
            if os.path.exists(edge_path):
                os.remove(edge_path)

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5  # Set a timeout to prevent the program from getting stuck
            )
            combined_output = ""
            if result.stdout:
                combined_output += result.stdout
            if result.stderr:
                if combined_output:
                    combined_output += "\n" + result.stderr
                else:
                    combined_output = result.stderr
            return combined_output.strip()
        except subprocess.TimeoutExpired:
            return "Error: Java process timed out."
        except Exception as e:
            return f"Error: Failed to run Java process. {e}"
