#!/usr/bin/env python3
"""Local-first check entry point; installation is an explicit owner action."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
sys.exit(subprocess.run([sys.executable, str(root / ".claude/run-checks.py")], cwd=root).returncode)
