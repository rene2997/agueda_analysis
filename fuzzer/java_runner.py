import subprocess
import json
import tempfile
import os
from typing import Tuple, Optional, Dict

class JavaRunner:
    def __init__(self, java_class_path: str, target_class: str, config, coverage_output_path: str = "coverage_temp.json"):
        """
        :param java_class_path: Java class path (e.g., "bin:lib/asm.jar", including instrumented class files)
        :param target_class: Target class name (e.g., "com.test.DivisionLoop")
        :param coverage_output_path: File path for the instrumented Java program to output coverage data (as previously agreed)
        """
        self.java_class_path = java_class_path
        self.target_class = target_class
        self.config = config # Pass in the FuzzerConfig object
        self.coverage_output_path = coverage_output_path
        # Ensure that there are no residual coverage output files
        if os.path.exists(coverage_output_path):
            os.remove(coverage_output_path)

    def run_java_program(self, input_data: int) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Run the instrumented Java program and return coverage data and exception information.
        :param input_data: Test case input (adapted to the int parameter of the Java program)
        :return: (coverage_data: dictionary of coverage branch lists, error_msg: exception information (None if none))
        """
        # 1. Construct the Java execution command (e.g., java -cp bin:lib/asm.jar com.test.DivisionLoop 1024)
        cmd = [
            "java",
            "-cp", self.java_class_path,
            self.target_class,
            str(input_data)  # Pass input parameters (Java program needs to read command line arguments)
        ]

        try:
            # 2. Execute the Java program and capture stdout (normal output) and stderr (exception output)
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5  # Timeout control (to avoid infinite loops)
            )

            # 3. Read exception information (exceptions thrown by the Java program will be printed to stderr)
            error_msg = None
            if result.returncode != 0:  # A non-zero return code indicates an execution exception
                error_msg = f"Java execution exception (return code {result.returncode}): {result.stderr.strip()}"

            # 4. Read coverage data (file written after the instrumented program is executed)
            coverage_data = None
            if os.path.exists(self.coverage_output_path):
                with open(self.coverage_output_path, "r", encoding="utf-8") as f:
                    coverage_data = json.load(f)  # Expected format: {"covered_branches": ["class:method:line:branchID", ...]}
                # Delete the temporary file after reading to avoid residuals
                os.remove(self.coverage_output_path)

            return coverage_data, error_msg

        except subprocess.TimeoutExpired:
            return None, f"Java program execution timed out (exceeded 5 seconds)"
        except Exception as e:
            return None, f"Python failed to call Java: {str(e)}"

    def run_java_program2(self, input_data: str):
        """
        Execute the Java program using the instrumentation agent and return the execution result.
        """
        # 1. Define the paths for the instrumentation agent and output files (read from the configuration)
        agent_path = self.config.agent_path
        shm_path = self.config.coverage_output_path
        map_path = self.config.map_output_path
        edge_path = self.config.edge_coverage_path

        # 2. Build the -javaagent parameter string
        agent_args = (
            f"-javaagent:{agent_path}="
            f"size=65536,"
            f"shm={os.path.abspath(shm_path)},"
            f"map={os.path.abspath(map_path)},"
            f"map.append=false,"
            f"perEdge=true,"
            f"perEdgePath={os.path.abspath(edge_path)}"
        )

        # 3. Build the complete Java execution command list
        command = [
            "java",
            agent_args,
            "-cp",
            self.java_class_path,
            self.target_class,
            str(input_data)  # Ensure the input is a string
        ]

        # 4. Execute the command
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
            # Return standard error because Java's exception stack is usually output to stderr
            return result.stderr
        except subprocess.TimeoutExpired:
            return "Error: Java process timed out."
        except Exception as e:
            return f"Error: Failed to run Java process. {e}"