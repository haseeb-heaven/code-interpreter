"""Single-file TOML model registry (replaces the old ``configs/*.json`` layout).

All model metadata that used to live in one JSON file per model
(``configs/<name>.json``) plus the curated free/cheap catalog
(``configs/free/catalog.json``) now lives in one human-editable file:
``configs/models.toml``.

Schema (see ``configs/models.toml`` for the full documented example)::

    schema_version = 1
    default_model = "gpt-4o"

    [[default_priority]]
    env = "OPENAI_API_KEY"
    model = "gpt-4o"

    [models."gemini-2.5-flash"]
    model = "gemini/gemini-2.5-flash"
    provider = "gemini"
    tier = "free_tier"
    temperature = 0.1
    max_tokens = 3072
    notes = "Gemini 2.5 Flash (Google AI Studio free tier)"

    [[free_catalog]]
    id = "gemini-2.5-flash"
    model_key = "gemini-2.5-flash"
    provider = "gemini"
    env_key = "GEMINI_API_KEY"
    tier = "free_tier"
    notes = "Gemini 2.5 Flash (Google AI Studio free tier)"

Users can add their own models/providers by editing this single file --
no Python code changes required.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional

try:  # Python 3.11+ stdlib
	import tomllib  # type: ignore
except ModuleNotFoundError:  # Python 3.10 fallback (CI still pins 3.10)
	import tomli as tomllib  # type: ignore

logger = logging.getLogger(__name__)

# Default location of the single-file model registry.
DEFAULT_REGISTRY_PATH = os.path.join("configs", "models.toml")

# Hard fallback when nothing else resolves (kept in sync with the
# ``default_model`` key at the top of ``configs/models.toml``).
_FALLBACK_DEFAULT_MODEL = "gpt-4o"

_lock = threading.Lock()
_cache: Dict[str, "ModelRegistry"] = {}


def _resolve_registry_path(path: Optional[str]) -> str:
	"""Normalize a registry path/dir argument to a concrete ``.toml`` file path."""
	candidate = path or DEFAULT_REGISTRY_PATH
	if os.path.isdir(candidate):
		return os.path.join(candidate, "models.toml")
	if not candidate.lower().endswith(".toml") and os.path.isdir(os.path.dirname(candidate) or "."):
		# Caller passed a bare directory-like string (e.g. "configs") that
		# does not yet exist as a real dir in this process' cwd view.
		maybe_dir = candidate
		maybe_file = os.path.join(maybe_dir, "models.toml")
		if os.path.isfile(maybe_file):
			return maybe_file
	return candidate


class ModelRegistry:
	"""Parsed view of a ``models.toml`` registry file."""

	def __init__(self, path: str, data: Dict[str, Any]):
		self.path = path
		self._data = data or {}
		self._models: Dict[str, Dict[str, Any]] = dict(self._data.get("models") or {})
		self._free_catalog: List[Dict[str, Any]] = list(self._data.get("free_catalog") or [])
		self._default_priority: List[Dict[str, Any]] = list(self._data.get("default_priority") or [])
		self._default_model = str(self._data.get("default_model") or _FALLBACK_DEFAULT_MODEL)

	# ── Loading ──────────────────────────────────────────────────────────

	@classmethod
	def load(cls, path: Optional[str] = None, *, use_cache: bool = True) -> "ModelRegistry":
		resolved = _resolve_registry_path(path)
		if use_cache:
			with _lock:
				cached = _cache.get(resolved)
				if cached is not None:
					try:
						mtime = os.path.getmtime(resolved)
					except OSError:
						mtime = None
					if cached._mtime == mtime:  # noqa: SLF001 (internal cache check)
						return cached

		data: Dict[str, Any] = {}
		try:
			with open(resolved, "rb") as handle:
				data = tomllib.load(handle)
		except FileNotFoundError:
			logger.warning("Model registry not found at %s; using empty registry.", resolved)
		except tomllib.TOMLDecodeError as exc:  # type: ignore[attr-defined]
			logger.error("Failed to parse model registry %s: %s", resolved, exc)

		registry = cls(resolved, data)
		try:
			registry._mtime = os.path.getmtime(resolved)  # noqa: SLF001
		except OSError:
			registry._mtime = None  # noqa: SLF001

		if use_cache:
			with _lock:
				_cache[resolved] = registry
		return registry

	@staticmethod
	def clear_cache() -> None:
		with _lock:
			_cache.clear()

	# ── Models ───────────────────────────────────────────────────────────

	def has_model(self, name: str) -> bool:
		return bool(name) and name in self._models

	def get_model(self, name: str) -> Optional[Dict[str, Any]]:
		"""Return a copy of the model dict for ``name``, or ``None``."""
		entry = self._models.get(name)
		if entry is None:
			return None
		return dict(entry)

	def list_model_names(self) -> List[str]:
		return sorted(self._models.keys())

	# ── Default model resolution ─────────────────────────────────────────

	def default_model_name(self, environ: Optional[Dict[str, str]] = None) -> str:
		env = environ if environ is not None else os.environ
		for row in self._default_priority:
			env_name = str(row.get("env") or "").strip()
			model_name = str(row.get("model") or "").strip()
			if env_name and model_name and env.get(env_name):
				return model_name
		return self._default_model

	# ── Free catalog ─────────────────────────────────────────────────────

	def free_catalog_entries(self) -> List[Dict[str, Any]]:
		"""Ordered list of curated free/cheap presets (raw dicts)."""
		return [dict(row) for row in self._free_catalog]


def get_model_registry(path: Optional[str] = None) -> ModelRegistry:
	"""Convenience accessor used by callers that don't need a custom path."""
	return ModelRegistry.load(path)
