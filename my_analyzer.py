import sys, pathlib

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.static_analysis.analysis import main

if __name__ == "__main__":
    sys.exit(main())
