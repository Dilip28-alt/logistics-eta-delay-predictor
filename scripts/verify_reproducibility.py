"""
Standalone verification script for Step 10: Fixed-seed reproducibility benchmarking.
Executes dual regeneration and performs bitwise SHA-256 hash validation across all exported artifacts.
"""

import os
import sys

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cli import cmd_reproduce


class Args:
    seed = 20261022


if __name__ == "__main__":
    print("Executing Standalone Step 10 Reproducibility Verification...")
    cmd_reproduce(Args())
