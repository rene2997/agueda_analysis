# fuzzer/error_detector.py (modified)
from typing import Optional, List, Dict, Set
import hashlib

class ErrorDetector:
    def __init__(self):
        self.errors: List[Dict] = []
        self.seen_errors: Set[str] = set()  # Use hashes to deduplicate and avoid recording the same error repeatedly

    def detect(self, input_data: int, error_msg: Optional[str]) -> bool:
        if not error_msg:
            return False

        # Generate a unique error identifier (based on the hash of the error message to avoid duplicates)
        error_hash = hashlib.md5(error_msg.encode("utf-8")).hexdigest()
        if error_hash in self.seen_errors:
            return False

        # Record error details (including Java input and exception information)
        self.seen_errors.add(error_hash)
        self.errors.append({
            "input": input_data,
            "error_message": error_msg,
            "error_type": self._extract_error_type(error_msg)  # Extract the error type (e.g., AssertionError)
        })
        return True

    def _extract_error_type(self, error_msg: str) -> str:
        """Extract the error type from the Java exception message (e.g., "java.lang.AssertionError")"""
        if "Exception" in error_msg or "Error" in error_msg:
            # The Java exception format is usually "Exception in thread "main" class_name: message"
            for part in error_msg.split(":"):
                if part.strip().startswith(("java.lang.", "com.")):
                    return part.strip()
        return "UnknownError"

    def get_errors(self) -> List[Dict]:
        return self.errors

    def error_count(self) -> int:
        return len(self.errors)