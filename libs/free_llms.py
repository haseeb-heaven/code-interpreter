"""Free / cheap LLM catalog for Gemini-CLI-style agentic runs.

Loads ``configs/free/catalog.json`` and helps pick models that work without
paid cloud lock-in (OpenRouter free, Groq/Gemini free tiers, Ollama, HF).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

DEFAULT_CATALOG_PATH = os.path.join("configs", "free", "catalog.json")


@dataclass(frozen=True)
class FreeModelEntry:
	"""One curated free/cheap model preset."""

	id: str
	config: str
	provider: str
	env_key: Optional[str]
	tier: str
	notes: str = ""

	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> "FreeModelEntry":
		if not isinstance(data, dict):
			raise ValueError("Free model entry must be a dict")
		config = str(data.get("config") or data.get("id") or "").strip()
		if not config:
			raise ValueError("Free model entry missing config/id")
		return cls(
			id=str(data.get("id") or config).strip(),
			config=config,
			provider=str(data.get("provider") or "unknown").strip(),
			env_key=(str(data["env_key"]).strip() if data.get("env_key") else None),
			tier=str(data.get("tier") or "free").strip(),
			notes=str(data.get("notes") or "").strip(),
		)

	def is_available(self, environ: Optional[Dict[str, str]] = None) -> bool:
		"""Return True when the required key is present (local always available)."""
		if environ is None:
			try:
				from dotenv import load_dotenv

				load_dotenv(override=False)
			except Exception:
				pass
			env = os.environ
		else:
			env = environ
		if not self.env_key:
			return True
		value = env.get(self.env_key)
		return bool(value and str(value).strip())

	def config_exists(self, configs_dir: str = "configs") -> bool:
		path = os.path.join(configs_dir, f"{self.config}.json")
		return os.path.isfile(path)


class FreeLLMCatalog:
	"""Curated catalog of free/cheap interpreter model configs."""

	def __init__(self, entries: Sequence[FreeModelEntry]):
		self._entries: List[FreeModelEntry] = list(entries)

	@property
	def entries(self) -> List[FreeModelEntry]:
		return list(self._entries)

	def __len__(self) -> int:
		return len(self._entries)

	@classmethod
	def load(cls, catalog_path: Optional[str] = None) -> "FreeLLMCatalog":
		"""Load catalog JSON; returns empty catalog on missing/invalid file."""
		path = catalog_path or DEFAULT_CATALOG_PATH
		try:
			with open(path, "r", encoding="utf-8") as handle:
				payload = json.load(handle)
		except FileNotFoundError:
			logger.warning("Free LLM catalog not found at %s", path)
			return cls([])
		except (OSError, json.JSONDecodeError) as exc:
			logger.error("Failed to load free LLM catalog %s: %s", path, exc)
			return cls([])

		raw_models = payload.get("models") if isinstance(payload, dict) else None
		if not isinstance(raw_models, list):
			logger.error("Free LLM catalog missing models list: %s", path)
			return cls([])

		entries: List[FreeModelEntry] = []
		for item in raw_models:
			try:
				entries.append(FreeModelEntry.from_dict(item))
			except ValueError as exc:
				logger.warning("Skipping invalid free model entry: %s", exc)
		return cls(entries)

	def list_ids(self) -> List[str]:
		return [entry.id for entry in self._entries]

	def list_configs(self) -> List[str]:
		return [entry.config for entry in self._entries]

	def get(self, name: str) -> Optional[FreeModelEntry]:
		needle = (name or "").strip().lower()
		if not needle:
			return None
		for entry in self._entries:
			if entry.id.lower() == needle or entry.config.lower() == needle:
				return entry
		return None

	def available(
		self,
		environ: Optional[Dict[str, str]] = None,
		configs_dir: str = "configs",
		require_config_file: bool = True,
	) -> List[FreeModelEntry]:
		"""Entries whose API key (if any) is set and config file exists."""
		result: List[FreeModelEntry] = []
		for entry in self._entries:
			if require_config_file and not entry.config_exists(configs_dir):
				continue
			if entry.is_available(environ):
				result.append(entry)
		return result

	def pick_default(
		self,
		environ: Optional[Dict[str, str]] = None,
		configs_dir: str = "configs",
		preferred: Optional[Iterable[str]] = None,
	) -> Optional[str]:
		"""Pick first available free config; optional preferred order by id/config."""
		available = self.available(environ=environ, configs_dir=configs_dir)
		if not available:
			return None

		if preferred:
			by_key = {}
			for entry in available:
				by_key[entry.id.lower()] = entry.config
				by_key[entry.config.lower()] = entry.config
			for name in preferred:
				hit = by_key.get(str(name).strip().lower())
				if hit:
					return hit

		return available[0].config

	def format_table(
		self,
		environ: Optional[Dict[str, str]] = None,
		configs_dir: str = "configs",
		only_available: bool = False,
	) -> str:
		"""Human-readable table for ``--list-free`` / ``/free``."""
		rows = self.available(environ=environ, configs_dir=configs_dir) if only_available else self._entries
		if not rows:
			return "No free LLM presets found."

		lines = [
			"Free / cheap LLM presets (configs/free/catalog.json):",
			"",
			f"{'#':<3} {'Config':<36} {'Provider':<12} {'Tier':<10} {'Ready':<6} Notes",
			"-" * 100,
		]
		for index, entry in enumerate(rows, 1):
			ready = "yes" if entry.is_available(environ) and entry.config_exists(configs_dir) else "no"
			notes = entry.notes[:40]
			lines.append(
				f"{index:<3} {entry.config:<36} {entry.provider:<12} {entry.tier:<10} {ready:<6} {notes}"
			)
		lines.append("")
		lines.append("Tip: python interpreter.py --gemini-style -m <config>")
		lines.append("     python interpreter.py --list-free")
		return "\n".join(lines)


def resolve_free_model(
	explicit_model: Optional[str] = None,
	prefer_free: bool = False,
	environ: Optional[Dict[str, str]] = None,
	catalog: Optional[FreeLLMCatalog] = None,
	configs_dir: str = "configs",
) -> Optional[str]:
	"""Resolve model when ``--free`` / ``--gemini-style`` should prefer free presets.

	- If ``explicit_model`` is set, return it unchanged (caller already chose).
	- Else if ``prefer_free``, return first available free catalog config.
	- Else return None (caller keeps existing default logic).
	"""
	if explicit_model:
		return explicit_model
	if not prefer_free:
		return None
	cat = catalog or FreeLLMCatalog.load()
	return cat.pick_default(environ=environ, configs_dir=configs_dir)
