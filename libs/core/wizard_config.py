# -*- coding: utf-8 -*-
"""Persisted no-args TUI wizard preferences across CLI runs.

Mirrors the on-disk convention already used by ``libs/memory/session_store.py``
(JSON files under ``~/.code-interpreter/``) so this feature does not invent a
second persistence mechanism. The wizard (``libs/terminal_ui.py``) collects the
same answers whether it runs interactively or is skipped in favour of a saved
file; only the *source* of the values changes.

File location: ``~/.code-interpreter/config.json`` (``default_config_path()``;
overridable per-instance, mainly for tests).

Schema::

    {
        "schema_version": 1,
        "settings": {
            "mode": "code",
            "model": "openrouter-free",
            ...
        }
    }

Only the non-secret preference fields the wizard already asks for are ever
written (see ``WIZARD_CONFIG_FIELDS``) -- model/session are stored by *name*,
never an API key or other credential value.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# Preference fields collected by TerminalUI.launch() / _collect_core_settings()
# / _collect_advanced_settings() that are safe to persist. Deliberately excludes
# one-shot data (--task/-f text) and anything secret-shaped (API keys never
# flow through the wizard onto args in the first place).
WIZARD_CONFIG_FIELDS = (
	"mode",
	"model",
	"lang",
	"display_code",
	"exec",
	"save_code",
	"history",
	"agentic",
	"agent",
	"gemini_style",
	"free",
	"stream",
	"search",
	"output_format",
	"safety",
	"sandbox",
	"sandbox_backend",
	"unsafe",
	"session",
	"yolo",
	"yes",
	"science",
	"interactive_charts",
	"image",
	"attach",
	"mcp_server",
)

# Modes that require one-shot ``--task``/``-f`` data which is never persisted;
# a saved config in one of these modes can't be safely auto-applied (it would
# hit resolve_codegen_task()'s "no task" error), so callers should fall back
# to running the wizard instead.
CODEGEN_MODES = ("generate", "project")


def default_config_path() -> Path:
	"""Resolve ``~/.code-interpreter/config.json`` (falls back when home is unavailable)."""
	try:
		return Path.home() / ".code-interpreter" / "config.json"
	except Exception:
		return Path(".code-interpreter") / "config.json"


# Mutable module default so tests can ``patch(...CONFIG_PATH, tmp)``.
CONFIG_PATH = default_config_path()


class WizardConfigStore:
	"""Persists non-secret wizard preferences to disk as JSON."""

	def __init__(self, path: Optional[Path] = None):
		self.path = Path(path) if path is not None else CONFIG_PATH

	def load(self) -> Optional[Dict[str, Any]]:
		"""Return the persisted, filtered settings dict, or ``None`` if missing/invalid/empty."""
		if not self.path.exists():
			return None
		try:
			data = json.loads(self.path.read_text(encoding="utf-8"))
		except (json.JSONDecodeError, OSError, TypeError, ValueError) as exc:
			logger.warning("[WizardConfig] Corrupt config file %s: %s. Ignoring.", self.path, exc)
			return None
		settings = data.get("settings") if isinstance(data, dict) else None
		if not isinstance(settings, dict) or not settings:
			return None
		filtered = {key: settings[key] for key in WIZARD_CONFIG_FIELDS if key in settings}
		return filtered or None

	def save(self, settings: Dict[str, Any]) -> None:
		"""Persist the wizard-collected preference fields to disk (never secrets)."""
		payload = {key: settings[key] for key in WIZARD_CONFIG_FIELDS if key in settings}
		if not payload:
			return
		try:
			self.path.parent.mkdir(parents=True, exist_ok=True)
			data = {"schema_version": SCHEMA_VERSION, "settings": payload}
			self.path.write_text(
				json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
			)
			logger.debug("[WizardConfig] Saved wizard preferences to %s", self.path)
		except OSError as exc:
			logger.warning("[WizardConfig] Failed to save config to %s: %s", self.path, exc)

	def clear(self) -> None:
		"""Delete the persisted config file, if any."""
		if self.path.exists():
			self.path.unlink()

	def exists(self) -> bool:
		return self.path.exists()


def apply_wizard_config_to_args(args: Any, settings: Dict[str, Any]) -> None:
	"""Copy persisted preference fields onto ``args`` (bare-invocation skip-wizard path)."""
	for key, value in settings.items():
		if key in WIZARD_CONFIG_FIELDS:
			setattr(args, key, value)


def settings_from_namespace(args: Any) -> Dict[str, Any]:
	"""Extract the persistable preference fields from a resolved args Namespace."""
	return {key: getattr(args, key) for key in WIZARD_CONFIG_FIELDS if hasattr(args, key)}
