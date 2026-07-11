"""Execution audit trail (JSONL) (#225)."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

AUDIT_LOG_PATH = Path.home() / ".code_interpreter" / "audit.jsonl"


def _hash(code: str) -> str:
	return hashlib.sha256((code or "").encode("utf-8", errors="replace")).hexdigest()[:16]


def audit_log_path() -> Path:
	return AUDIT_LOG_PATH


def log_execution(
	task: str,
	code: str,
	output: str,
	model: str,
	language: str,
	safety_blocked: bool = False,
	sandbox: str = "subprocess",
	duration_ms: Optional[int] = None,
	*,
	path: Optional[Path] = None,
) -> dict[str, Any]:
	"""
	Append a single JSON line to the audit log.
	Stores a code hash (not raw code) for privacy.
	"""
	target = path or AUDIT_LOG_PATH
	try:
		target.parent.mkdir(parents=True, exist_ok=True)
	except Exception as exc:
		logger.warning("Could not create audit log dir: %s", exc)
		return {}

	entry = {
		"ts": datetime.now(timezone.utc).isoformat(),
		"task": (task or "")[:500],
		"model": model or "",
		"language": language or "",
		"sandbox": sandbox or "subprocess",
		"code_hash": _hash(code),
		"code_lines": (code or "").count("\n") + (1 if code else 0),
		"output_lines": (output or "").count("\n") + (1 if output else 0),
		"safety_blocked": bool(safety_blocked),
		"duration_ms": duration_ms,
	}
	# Never persist secrets in the audit trail.
	blob = json.dumps(entry, ensure_ascii=False)
	lower = blob.lower()
	if "sk-" in lower or "api_key" in lower:
		entry["task"] = "[redacted]"
		blob = json.dumps(entry, ensure_ascii=False)

	try:
		with open(target, "a", encoding="utf-8") as fh:
			fh.write(blob + "\n")
	except Exception as exc:
		logger.warning("Failed to write audit log: %s", exc)
	return entry


def read_recent(limit: int = 10, *, path: Optional[Path] = None) -> list[dict]:
	"""Return the last ``limit`` audit entries (oldest→newest within the window)."""
	target = path or AUDIT_LOG_PATH
	if not target.is_file():
		return []
	try:
		lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
	except Exception as exc:
		logger.warning("Failed to read audit log: %s", exc)
		return []
	entries: list[dict] = []
	for line in lines[-max(int(limit), 0) :]:
		line = line.strip()
		if not line:
			continue
		try:
			entries.append(json.loads(line))
		except json.JSONDecodeError:
			continue
	return entries


def clear_audit(*, path: Optional[Path] = None) -> bool:
	"""Delete the audit log file. Returns True if removed or absent."""
	target = path or AUDIT_LOG_PATH
	try:
		if target.is_file():
			target.unlink()
		return True
	except Exception as exc:
		logger.warning("Failed to clear audit log: %s", exc)
		return False


def format_recent(limit: int = 10, *, path: Optional[Path] = None) -> str:
	rows = read_recent(limit, path=path)
	if not rows:
		return "No audit entries yet."
	lines = ["ts | task | model | sandbox | duration_ms | blocked"]
	for e in rows:
		lines.append(
			f"{e.get('ts', '')} | {e.get('task', '')[:60]} | {e.get('model', '')} | "
			f"{e.get('sandbox', '')} | {e.get('duration_ms', '')} | {e.get('safety_blocked', False)}"
		)
	return "\n".join(lines)
