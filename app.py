"""Launch the React + Flask application from the repository root."""

import os
import runpy
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent / "anxin"


def main():
    if str(PROJECT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_DIR))
    os.chdir(PROJECT_DIR)
    runpy.run_path(str(PROJECT_DIR / "app.py"), run_name="__main__")


if __name__ == "__main__":
    main()
