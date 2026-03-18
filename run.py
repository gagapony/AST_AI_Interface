#!/usr/bin/env python3
"""Run clang-call-analyzer as a module."""

import sys
import os
from pathlib import Path

# Change to project directory
os.chdir(str(Path(__file__).parent))

# Run as module
if __name__ == "__main__":
    import subprocess
    cmd = [sys.executable, "-m", "src.cli"] + sys.argv[1:]
    sys.exit(subprocess.run(cmd).returncode)
