# -*- coding: utf-8 -*-
"""Persistent conversation sessions across CLI runs (#218)."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SAFE_SESSION_ID = re.compile(r"^[A-Za-z0-9._-]+$")


def default_session_dir() -> Path:
	"""Resolve ``~/.code-interpreter/sessions`` (falls back when home is unavailable)."""
	try:
		return Path.home() / ".code-interpreter" / "sessions"
	except Exception:
		return Path(".code-interpreter") / "sessions"


# Mutable module default so tests can ``patch(...SESSION_DIR, tmp)``.
# Computed at import with a fallback so ``patch.dict(..., clear=True)`` cannot
# break subsequent imports that load this module.
SESSION_DIR = default_session_dir()


def sanitize_session_id(session_id: str) -> str:
	"""Return a filesystem-safe session id or raise ValueError."""
	cleaned = (session_id or "").strip()
	if not cleaned or not _SAFE_SESSION_ID.match(cleaned):
		raise ValueError(
			"Invalid session id. Use letters, digits, dots, underscores, or hyphens only."
		)
	if cleaned in (".", ".."):
		raise ValueError("Invalid session id.")
	return cleaned


class SessionStore:
	"""
	Persists conversation message history to disk as JSON.

	Each session is stored at ``~/.code-interpreter/sessions/<session_id>.json``
	(or a custom ``session_dir`` for tests).

	Session file schema::

	    {
	        "session_id": "my-project",
	        "created_at": 1720000000,
	        "updated_at": 1720001234,
	        "model": "gpt-4o",
	        "messages": [ ... ]
	    }
	"""

	def __init__(self, session_id: str = "default", session_dir: Optional[Path] = None):
		self.session_id = sanitize_session_id(session_id)
		self.session_dir = Path(session_dir) if session_dir is not None else SESSION_DIR
		self.session_dir.mkdir(parents=True, exist_ok=True)
		self.path = self.session_dir / f"{self.session_id}.json"

	def load(self) -> list:
		"""Load messages from disk. Returns empty list if session doesn't exist."""
		if not self.path.exists():
			logger.info(f"[Session] No existing session: {self.session_id}")
			return []
		try:
			data = json.loads(self.path.read_text(encoding="utf-8"))
			messages = data.get("messages", [])
			if not isinstance(messages, list):
				logger.warning(
					f"[Session] Corrupt session file {self.path}: messages not a list. Starting fresh."
				)
				return []
			logger.info(
				f"[Session] Loaded '{self.session_id}' — {len(messages)} messages"
			)
			return messages
		except (json.JSONDecodeError, OSError, TypeError) as exc:
			logger.warning(
				f"[Session] Corrupt session file {self.path}: {exc}. Starting fresh."
			)
			return []

	def save(self, messages: list, model: str = "") -> None:
		"""Save messages to disk. Creates or overwrites the session file."""
		if not messages:
			return

		existing = {}
		if self.path.exists():
			try:
				existing = json.loads(self.path.read_text(encoding="utf-8"))
			except Exception:
				existing = {}

		data = {
			"session_id": self.session_id,
			"created_at": existing.get("created_at", int(time.time())),
			"updated_at": int(time.time()),
			"model": model or existing.get("model", ""),
			"messages": messages,
		}
		self.path.write_text(
			json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
		)
		logger.debug(
			f"[Session] Saved '{self.session_id}' — {len(messages)} messages"
		)

	def clear(self) -> None:
		"""Delete the session file."""
		if self.path.exists():
			self.path.unlink()
			logger.info(f"[Session] Cleared '{self.session_id}'")

	def exists(self) -> bool:
		return self.path.exists()

	def get_metadata(self) -> Optional[dict]:
		"""Return session metadata without loading all messages."""
		if not self.path.exists():
			return None
		try:
			data = json.loads(self.path.read_text(encoding="utf-8"))
			return {
				"session_id": data.get("session_id"),
				"created_at": data.get("created_at"),
				"updated_at": data.get("updated_at"),
				"model": data.get("model", ""),
				"message_count": len(data.get("messages", [])),
			}
		except Exception:
			return None

	@staticmethod
	def list_sessions(session_dir: Optional[Path] = None) -> list:
		"""List all saved sessions with metadata, sorted by last updated."""
		root = Path(session_dir) if session_dir is not None else SESSION_DIR
		if not root.exists():
			return []
		sessions = []
		for path in root.glob("*.json"):
			try:
				data = json.loads(path.read_text(encoding="utf-8"))
				sessions.append(
					{
						"session_id": data.get("session_id", path.stem),
						"updated_at": data.get("updated_at", 0),
						"model": data.get("model", "unknown"),
						"message_count": len(data.get("messages", [])),
					}
				)
			except Exception:
				continue
		return sorted(sessions, key=lambda item: item["updated_at"], reverse=True)

	@staticmethod
	def delete_session(session_id: str, session_dir: Optional[Path] = None) -> bool:
		"""Delete a saved session by id. Returns True if a file was removed."""
		sid = sanitize_session_id(session_id)
		root = Path(session_dir) if session_dir is not None else SESSION_DIR
		path = root / f"{sid}.json"
		if path.exists():
			path.unlink()
			return True
		return False
