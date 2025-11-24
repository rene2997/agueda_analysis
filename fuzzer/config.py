# fuzzer/config.py (modified)
class FuzzerConfig:
    def __init__(
        self,
        # Java-related configuration (fill in after discussion with classmates)
        java_class_path: str = "bin:lib/asm.jar",  # Java class path (including instrumented classes and ASM dependencies)
        target_class: str = "com.test.DivisionLoop",  # Target Java class name (including package name)
        # Original fuzz configuration
        timeout: float = 5.0,
        seed_count: int = 100,
        mutate_count: int = 5,
        max_iterations: int = 10000,
        coverage_map_size: int = 65536
    ):
        # Path to the compiled jar of the target Java project
        self.java_class_path = java_class_path

        # Target test Java class (with package name)
        self.target_class = target_class
        self.timeout = timeout
        self.seed_count = seed_count
        self.mutate_count = mutate_count
        self.max_iterations = max_iterations

        # --- New: Instrumentation-related configuration ---
        # Bitmap size
        self.coverage_map_size = coverage_map_size

        # It is recommended to use an absolute path or a path relative to the project root directory
        # Agent jar package
        self.agent_path = "./bytescribe-agent-1.0-SNAPSHOT.jar"
        self.coverage_output_path = "./bytescribe.cov"
        self.map_output_path = "./bytescribe-map.csv"
        self.edge_coverage_path = "./per-edge.csv"  # This is the most important file