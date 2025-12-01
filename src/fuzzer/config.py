# fuzzer/config.py (modified)
class FuzzerConfig:
    def __init__(
        self,
        # Java-related configuration
        java_class_path: str = "./jpamb/target/classes",  # Java classpath (including instrumented classes and ASM dependencies)
        target_method: str = "jpamb.cases.Simple.divideByN:(I)I",  # Target Java method for testing (with package name, class name, and input/output parameter types)
        guided_seeds: list = None,
        agent_path: str = "./bytescribe-agent-1.0-SNAPSHOT.jar", # Path to the instrumentation agent jar package
        # Original fuzz configuration
        timeout: float = 5.0,
        seed_count: int = 100,
        mutate_count: int = 5,
        max_iterations: int = 10000,
        coverage_map_size: int = 65536
    ):
        # Path to the compiled jar package of the target Java project
        self.java_class_path = java_class_path

        # Target Java method for testing (with package name, class name, and input/output parameter types)
        self.target_method = target_method
        self.guided_seeds = guided_seeds
        self.timeout = timeout
        self.seed_count = seed_count
        self.mutate_count = mutate_count
        self.max_iterations = max_iterations

        # --- New: Instrumentation-related configuration ---
        # Bitmap size
        self.coverage_map_size = coverage_map_size

        # It is recommended to use an absolute path or a path relative to the project root directory
        # Agent jar package
        self.agent_path = agent_path
        self.coverage_output_path = "./bytescribe.cov"
        self.map_output_path = "./bytescribe-map.csv"
        self.edge_coverage_path = "./per-edge.csv"