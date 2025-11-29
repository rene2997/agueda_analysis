import subprocess
import json
import tempfile
import os
from typing import Tuple, Optional, Dict

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
        if isinstance(input_data, tuple):
            # For a tuple (1, 2, 3), create the string "(1,2,3)"
            param_str = ",".join(map(str, input_data))
            formatted_input = f"({param_str})"
        else:
            # Compatible with single value cases, e.g., 42 -> "(42)"
            formatted_input = f"({input_data})"

        # 4. Build the complete Java execution command list
        command = [
            "java",
            agent_args,
            "-ea", # Enable assertions
            "-cp",
            self.java_class_path,
            self.runtime_class,
            self.target_method, # First argument: method signature
            formatted_input     # Second argument: formatted parameters required by the target method to be executed
        ]

        # 4.1 log
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
            # Return stderr because Java's exception stack traces are usually output to stderr
            return result.stderr
        except subprocess.TimeoutExpired:
            return "Error: Java process timed out."
        except Exception as e:
            return f"Error: Failed to run Java process. {e}"