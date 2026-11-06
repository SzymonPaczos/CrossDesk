#!/usr/bin/env python3
"""Run the owner's explicit argv lists, preserving failure and avoiding a shell."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", action="store_true", help="also run approved setup commands")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / ".claude/project-checks.json").read_text())
    commands = config["verification_commands"]
    if args.setup:
        commands = config["setup_commands"] + commands
    if not commands or any(not isinstance(argv, list) or not argv or
                           any(not isinstance(s, str) or not s for s in argv)
                           for argv in commands):
        print("BLOCKED: invalid or missing explicit check commands", file=sys.stderr)
        return 2
    for index, argv in enumerate(commands, 1):
        try:
            result = subprocess.run(argv, cwd=root, check=False)
        except OSError as error:
            print(f"CHECK {index}: BLOCKED ({type(error).__name__})", file=sys.stderr)
            return 2
        print(f"CHECK {index}: exit={result.returncode}", flush=True)
        if result.returncode:
            return result.returncode if result.returncode > 0 else 128 - result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
