#!/usr/bin/env python3
"""
Non-interactive end-to-end CLI verification for feature branch agents.

Runs without human input. Exit code 0 = all checks passed.

Usage:
  python scripts/run_e2e_cli.py
  python scripts/run_e2e_cli.py --quick
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, timeout: int = 300) -> None:
    print(f"\n==> {' '.join(cmd)}")
    env = os.environ.copy()
    env["INTERPRETER_YES"] = "1"
    env["CI"] = env.get("CI") or "true"
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        env=env,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise SystemExit(f"FAILED ({proc.returncode}): {' '.join(cmd)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run non-interactive agent CLI e2e suite")
    parser.add_argument("--quick", action="store_true", help="Skip full unittest discover")
    args = parser.parse_args()
    py = sys.executable

    # 1) Flag surface
    run([py, str(ROOT / "interpreter.py"), "--help"])
    run([py, str(ROOT / "interpreter.py"), "--version"])

    # 2) Dedicated non-interactive e2e tests
    run(
        [
            py,
            "-m",
            "pytest",
            "tests/e2e/test_cli_noninteractive.py",
            "tests/test_react_e2e.py",
            "tests/test_react_cli.py",
            "tests/agents/test_agent_pipeline.py",
            "tests/test_react_controller.py",
            "-q",
            "--tb=short",
        ],
        timeout=180,
    )

    if not args.quick:
        # 3) Full unit suite (still non-interactive)
        run([py, "-m", "pytest", "tests/", "-q", "--tb=line"], timeout=600)

    print("\nE2E CLI suite PASSED (no human input required).")
    print("Example scripted commands:")
    print("  python interpreter.py --agent  --yes --cli -m gpt-4o -f task.txt")
    print("  python interpreter.py --agentic --yes --cli -m gpt-4o -f task.txt")


if __name__ == "__main__":
    main()
