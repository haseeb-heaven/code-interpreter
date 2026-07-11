"""Optional Docker sandbox for strong isolation (#225)."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_IMAGE = "python:3.12-slim"


def is_docker_available() -> bool:
	"""Return True when the Docker daemon responds to ``docker info``."""
	try:
		subprocess.run(
			["docker", "info"],
			capture_output=True,
			check=True,
			timeout=3,
		)
		return True
	except Exception:
		return False


def run_in_docker(
	code: str,
	timeout: int = 30,
	image: str = DEFAULT_IMAGE,
	allow_network: bool = False,
	memory_mb: int = 512,
) -> dict[str, Any]:
	"""
	Run Python code in a Docker container with read-only root FS,
	optional network disable, memory cap, and auto-remove.
	"""
	if not code or not str(code).strip():
		return {
			"stdout": "",
			"stderr": "Code is empty.",
			"returncode": -1,
			"timed_out": False,
		}

	fd, host_path = tempfile.mkstemp(suffix=".py")
	try:
		with os.fdopen(fd, "w", encoding="utf-8") as fh:
			fh.write(code)
	except Exception:
		os.close(fd)
		raise

	try:
		cmd = [
			"docker",
			"run",
			"--rm",
			"--read-only",
			"--tmpfs",
			"/tmp:rw,size=100m",
			f"--memory={int(memory_mb)}m",
			"--cpus=1.0",
			"--security-opt",
			"no-new-privileges",
			"--cap-drop=ALL",
		]
		if not allow_network:
			cmd += ["--network=none"]
		cmd += [
			"-v",
			f"{host_path}:/code/script.py:ro",
			"-w",
			"/code",
			image,
			"python",
			"/code/script.py",
		]
		result = subprocess.run(
			cmd,
			capture_output=True,
			text=True,
			timeout=max(int(timeout) + 5, 10),
		)
		return {
			"stdout": result.stdout or "",
			"stderr": result.stderr or "",
			"returncode": result.returncode,
			"timed_out": False,
		}
	except subprocess.TimeoutExpired:
		logger.warning("Docker execution timed out")
		return {
			"stdout": "",
			"stderr": "Docker execution timed out",
			"returncode": -1,
			"timed_out": True,
		}
	except FileNotFoundError:
		return {
			"stdout": "",
			"stderr": (
				"Docker not found. Install Docker Desktop / Engine, or use "
				"--sandbox subprocess (default)."
			),
			"returncode": -1,
			"timed_out": False,
		}
	except Exception as exc:
		logger.exception("Docker sandbox failed")
		return {
			"stdout": "",
			"stderr": str(exc),
			"returncode": -1,
			"timed_out": False,
		}
	finally:
		try:
			os.unlink(host_path)
		except OSError:
			pass
