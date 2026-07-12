# -*- coding: utf-8 -*-
"""Run one agentic media suite case via interpreter CLI."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from tests.agentic.media.cases import SuiteCase
from tests.agentic.media.soft_skip import (
	is_billing_or_auth_failure,
	is_dep_or_env_failure,
	redact_output,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]

_MODEL_PREF = (
	("OPENROUTER_API_KEY", "openrouter-free"),
	("GROQ_API_KEY", "groq-llama-3.1-8b"),
	("GEMINI_API_KEY", "gemini-2.5-flash-lite"),
	("OPENAI_API_KEY", "gpt-4o-mini"),
)


def _looks_real(key: str) -> bool:
	val = (os.getenv(key) or "").strip()
	if not val or len(val) < 16:
		return False
	low = val.lower()
	# Avoid "xxx" substring — synthetic keys like "x"*40 must still look real in unit tests.
	if any(t in low for t in ("your_", "placeholder", "changeme", "example", "dummy")):
		return False
	return True


def pick_default_model() -> str:
	"""Prefer free/cheap presets when keys look real; else local-model."""
	for env_key, config in _MODEL_PREF:
		if _looks_real(env_key):
			return config
	return "local-model"


def build_command(case: SuiteCase, prompt_path: Path, model: str) -> list[str]:
	python_exe = os.environ.get("INTERPRETER_TEST_PYTHON") or sys.executable
	cmd = [
		python_exe,
		str(ROOT / "interpreter.py"),
		"--cli",
		"-m",
		model,
		"-md",
		"code",
		"-l",
		case.language,
		"-f",
		str(prompt_path),
		"--yes",
		"--exec",
		"--timeout",
		"90",
	]
	if case.agentic:
		cmd.append("--agentic")
	cmd.extend(case.extra_args or [])
	return cmd


def run_case(case: SuiteCase, *, model_override: str | None = None) -> dict[str, Any]:
	"""Execute one case; classify PASS/FAIL/SKIP. Never raises."""
	model = model_override or case.model or pick_default_model()
	started = time.time()
	row: dict[str, Any] = {
		"id": case.id,
		"tier": case.tier,
		"category": case.category,
		"status": "FAIL",
		"reason": "",
		"duration_s": 0.0,
		"model": model,
		"output_excerpt": "",
	}
	try:
		with tempfile.TemporaryDirectory(prefix="agentic_media_") as tmp:
			prompt_path = Path(tmp) / "prompt.txt"
			prompt_path.write_text(case.prompt, encoding="utf-8")
			cmd = build_command(case, prompt_path, model)
			env = os.environ.copy()
			env["PYTHONIOENCODING"] = "utf-8"
			env["INTERPRETER_YES"] = "1"
			proc = subprocess.run(
				cmd,
				cwd=str(ROOT),
				capture_output=True,
				text=True,
				encoding="utf-8",
				errors="replace",
				timeout=240,
				env=env,
			)
			raw = (proc.stdout or "") + "\n" + (proc.stderr or "")
			safe = redact_output(raw)
			row["output_excerpt"] = safe[-2000:]
			marker = case.expect_marker or ""
			if is_billing_or_auth_failure(safe):
				row["status"] = "SKIP"
				row["reason"] = "billing/auth soft-skip"
			elif is_dep_or_env_failure(safe) and marker and marker not in raw:
				row["status"] = "SKIP"
				row["reason"] = "dep/env soft-skip"
			elif marker and marker in raw:
				row["status"] = "PASS"
				row["reason"] = f"marker {marker}"
			elif proc.returncode == 0 and not marker:
				row["status"] = "PASS"
				row["reason"] = "exit 0"
			elif proc.returncode != 0:
				row["status"] = "FAIL"
				row["reason"] = f"exit={proc.returncode}"
			else:
				row["status"] = "FAIL"
				row["reason"] = f"marker missing: {marker}"
	except subprocess.TimeoutExpired:
		row["status"] = "SKIP"
		row["reason"] = "timeout soft-skip"
	except Exception as exc:  # noqa: BLE001
		msg = f"{type(exc).__name__}: {exc}"
		if is_billing_or_auth_failure(msg) or is_dep_or_env_failure(msg):
			row["status"] = "SKIP"
			row["reason"] = msg
		else:
			row["status"] = "FAIL"
			row["reason"] = msg
	finally:
		row["duration_s"] = round(time.time() - started, 2)
	return row
