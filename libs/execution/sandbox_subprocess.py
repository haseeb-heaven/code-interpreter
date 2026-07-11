"""Subprocess isolation for generated code (#225)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30
DEFAULT_MEMORY_MB = 512


def _set_memory_limit(memory_mb: int = DEFAULT_MEMORY_MB) -> None:
	"""Apply RLIMIT_AS in the child process (Unix only)."""
	try:
		import resource

		limit = int(memory_mb) * 1024 * 1024
		resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
	except Exception as exc:  # pragma: no cover - platform variance
		logger.debug("Memory limit not applied: %s", exc)


def _suffix(lang: str) -> str:
	return {"python": ".py", "bash": ".sh", "javascript": ".js", "r": ".R"}.get(
		(lang or "python").lower(), ".txt"
	)


def _build_command(path: str, lang: str) -> list[str]:
	lang = (lang or "python").lower()
	mapping = {
		"python": [sys.executable, path],
		"bash": ["bash", path],
		"javascript": ["node", path],
		"r": ["Rscript", path],
	}
	return mapping.get(lang, [sys.executable, path])


def run_in_subprocess(
	code: str,
	timeout: int = DEFAULT_TIMEOUT,
	language: str = "python",
	working_dir: str | None = None,
	memory_mb: int = DEFAULT_MEMORY_MB,
) -> dict[str, Any]:
	"""
	Execute code in an isolated child subprocess.

	Returns dict with stdout, stderr, returncode, timed_out.
	"""
	if not code or not str(code).strip():
		return {
			"stdout": "",
			"stderr": "Code is empty.",
			"returncode": -1,
			"timed_out": False,
		}

	workdir = working_dir or str(Path.cwd())
	fd, tmp_path = tempfile.mkstemp(suffix=_suffix(language), dir=workdir)
	try:
		with os.fdopen(fd, "w", encoding="utf-8") as fh:
			fh.write(code)
	except Exception:
		os.close(fd)
		raise

	try:
		cmd = _build_command(tmp_path, language)
		kwargs: dict[str, Any] = {
			"capture_output": True,
			"text": True,
			"timeout": timeout,
			"cwd": workdir,
		}
		if sys.platform != "win32":
			kwargs["preexec_fn"] = lambda: _set_memory_limit(memory_mb)

		result = subprocess.run(cmd, **kwargs)
		return {
			"stdout": result.stdout or "",
			"stderr": result.stderr or "",
			"returncode": result.returncode,
			"timed_out": False,
		}
	except subprocess.TimeoutExpired:
		logger.warning("Subprocess timed out after %ss", timeout)
		return {
			"stdout": "",
			"stderr": f"Execution timed out after {timeout}s. Retry with --timeout {timeout * 2}.",
			"returncode": -1,
			"timed_out": True,
		}
	except Exception as exc:
		logger.exception("Subprocess execution failed")
		return {
			"stdout": "",
			"stderr": str(exc),
			"returncode": -1,
			"timed_out": False,
		}
	finally:
		try:
			os.unlink(tmp_path)
		except OSError:
			pass
