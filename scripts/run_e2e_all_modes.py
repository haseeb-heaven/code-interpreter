#!/usr/bin/env python3
"""Run offline + live smoke and all-mode e2e (non-interactive)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(cmd: list[str], *, timeout: int = 900) -> None:
    print(f"\n==> {' '.join(cmd)}")
    env = os.environ.copy()
    env["INTERPRETER_YES"] = "1"
    env["CI"] = env.get("CI") or "true"
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(cmd, cwd=str(ROOT), env=env, timeout=timeout)
    if proc.returncode != 0:
        raise SystemExit(f"FAILED ({proc.returncode}): {' '.join(cmd)}")


def main() -> None:
    run([PY, str(ROOT / "scripts" / "report_key_presence.py")], timeout=60)
    run([PY, str(ROOT / "scripts" / "smoke_all_models.py")], timeout=600)
    # Live matrix for all configs with real keys (skips missing/expensive)
    env_live = os.environ.copy()
    env_live["SMOKE_LIVE"] = "1"
    env_live["PYTHONIOENCODING"] = "utf-8"
    print("\n==> live smoke_all_models")
    proc = subprocess.run(
        [PY, str(ROOT / "scripts" / "smoke_all_models.py"), "--live"],
        cwd=str(ROOT),
        env=env_live,
        timeout=1800,
    )
    if proc.returncode != 0:
        print(f"WARNING: live smoke exited {proc.returncode} (continuing e2e unit tests)")

    run(
        [
            PY,
            "-m",
            "pytest",
            "tests/e2e/",
            "tests/test_key_manager.py",
            "tests/test_rate_limiter.py",
            "tests/test_circuit_breaker.py",
            "tests/test_e2e_retry.py",
            "-q",
            "--tb=short",
        ],
        timeout=900,
    )
    print("\nE2E / smoke harness finished.")


if __name__ == "__main__":
    main()
