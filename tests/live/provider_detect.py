"""Detect providers/runtimes for the live matrix without exposing secrets.

Never log or return API key values — only names and present/absent.
"""

from __future__ import annotations

import logging
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from libs.core.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env", override=True)

FAMILY_REPS: list[dict[str, Any]] = [
	{"id": "openai", "config": "gpt-4o-mini", "env_key": "OPENAI_API_KEY"},
	{"id": "anthropic", "config": "claude-haiku-4-5", "env_key": "ANTHROPIC_API_KEY"},
	{"id": "gemini", "config": "gemini-2.5-flash", "env_key": "GEMINI_API_KEY"},
	{"id": "groq", "config": "groq-llama-3.1-8b", "env_key": "GROQ_API_KEY"},
	{"id": "openrouter", "config": "openrouter-free", "env_key": "OPENROUTER_API_KEY"},
	{"id": "huggingface", "config": "hf-meta-llama-3", "env_key": "HUGGINGFACE_API_KEY"},
	{"id": "local", "config": "local-model", "env_key": None},
]

_PLACEHOLDER_TOKENS = (
	"your_",
	"changeme",
	"placeholder",
	"example",
	"dummy",
)


def looks_real(key_name: str | None) -> bool:
	"""Return True when env var looks like a real key (never returns the value)."""
	if key_name is None:
		return True
	value = (os.getenv(key_name) or "").strip()
	if not value or len(value) < 16:
		return False
	low = value.lower()
	if any(tok in low for tok in _PLACEHOLDER_TOKENS):
		return False
	# Reject only well-known stub values, not keys that merely contain digits.
	if key_name == "OPENAI_API_KEY" and value in ("sk-1234567890", "sk-1234567890abcdef"):
		return False
	return True


def probe_local_endpoint(timeout: float = 1.5) -> bool:
	"""True when a local OpenAI-compatible endpoint answers /v1/models."""
	bases: list[str] = []
	try:
		data = ModelRegistry.load(str(ROOT / "configs")).get_model("local-model")
		api_base = str((data or {}).get("api_base") or "").rstrip("/")
		if api_base:
			bases.append(api_base)
	except OSError as exc:
		logger.debug("local-model registry entry unreadable: %s", exc)
	for fallback in (
		"http://127.0.0.1:11434/v1",
		"http://localhost:11434/v1",
		"http://127.0.0.1:1234/v1",
	):
		if fallback not in bases:
			bases.append(fallback)

	for base in bases:
		url = f"{base.rstrip('/')}/models"
		try:
			with urllib.request.urlopen(url, timeout=timeout) as resp:
				if 200 <= getattr(resp, "status", 200) < 300:
					return True
		except (urllib.error.URLError, TimeoutError, OSError) as exc:
			logger.debug("local probe miss %s: %s", url, type(exc).__name__)
	return False


def _load_free_catalog() -> list[dict[str, Any]]:
	try:
		registry = ModelRegistry.load(str(ROOT / "configs"))
	except OSError as exc:
		logger.warning("models.toml unreadable: %s", exc)
		return []
	entries = registry.free_catalog_entries()
	for entry in entries:
		entry.setdefault("config", entry.get("model_key") or entry.get("id"))
	return entries


def detect_providers() -> list[dict[str, Any]]:
	"""Return provider rows: id, config, env_key, available, source, optional tier.

	Never includes secret values.
	"""
	rows: list[dict[str, Any]] = []
	seen_ids: set[str] = set()

	local_up = probe_local_endpoint()
	for fam in FAMILY_REPS:
		pid = fam["id"]
		env_key = fam["env_key"]
		if pid == "local":
			available = local_up
		else:
			available = looks_real(env_key)
		rows.append(
			{
				"id": pid,
				"config": fam["config"],
				"env_key": env_key,
				"available": bool(available),
				"source": "local" if pid == "local" else "family",
			}
		)
		seen_ids.add(pid)

	for entry in _load_free_catalog():
		eid = str(entry.get("id") or entry.get("config") or "").strip()
		if not eid or eid in seen_ids:
			continue
		cfg = str(entry.get("config") or eid)
		env_key = entry.get("env_key")
		provider = str(entry.get("provider") or "").lower()
		if provider in ("local", "ollama", "lmstudio") or env_key is None:
			available = local_up
		else:
			available = looks_real(str(env_key))
		rows.append(
			{
				"id": eid,
				"config": cfg,
				"env_key": env_key,
				"available": bool(available),
				"source": "free_catalog",
				"tier": entry.get("tier"),
				"provider_family": provider,
			}
		)
		seen_ids.add(eid)

	return rows


def language_runtimes() -> dict[str, dict[str, Any]]:
	"""Report python / javascript / r runtime availability (no secrets)."""
	python_ok = True
	node = shutil.which("node")
	rscript = shutil.which("Rscript") or shutil.which("R")
	return {
		"python": {"available": python_ok, "command": "python"},
		"javascript": {"available": bool(node), "command": node or "node"},
		"r": {"available": bool(rscript), "command": rscript or "Rscript"},
	}


def resolve_test_data_dir(*, require: bool = False) -> Path | None:
	"""INTERPRETER_TEST_DATA_DIR (preferred) or TEST_DATA_DIR."""
	raw = (os.environ.get("INTERPRETER_TEST_DATA_DIR") or os.environ.get("TEST_DATA_DIR") or "").strip()
	if not raw:
		if require:
			raise RuntimeError(
				"Set INTERPRETER_TEST_DATA_DIR (or TEST_DATA_DIR) for matrix fixtures"
			)
		return None
	path = Path(raw).expanduser().resolve()
	path.mkdir(parents=True, exist_ok=True)
	return path
