# -*- coding: utf-8 -*-
"""Ollama detection and model picking for local-only runs (Issue #221)."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)

OLLAMA_API = "http://localhost:11434"
DEFAULT_PRIORITY: Sequence[str] = (
	"codellama",
	"llama3.1",
	"llama3",
	"mistral",
	"deepseek",
	"qwen",
	"phi",
)


class OllamaError(Exception):
	"""Raised when Ollama is unavailable or a model cannot be resolved."""


def is_ollama_running(base_url: str = OLLAMA_API, timeout: float = 2.0) -> bool:
	"""Return True when the Ollama HTTP API responds."""
	try:
		with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout) as resp:
			return 200 <= getattr(resp, "status", 200) < 300
	except Exception as exc:
		logger.debug("Ollama not reachable at %s: %s", base_url, exc)
		return False


def list_ollama_models(base_url: str = OLLAMA_API, timeout: float = 3.0) -> List[str]:
	"""Return locally installed Ollama model names (may be empty)."""
	try:
		with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=timeout) as resp:
			payload = json.loads(resp.read().decode("utf-8", errors="replace"))
		models = payload.get("models") or []
		names: List[str] = []
		for item in models:
			if isinstance(item, dict):
				name = item.get("name") or item.get("model")
				if name:
					names.append(str(name))
			elif isinstance(item, str):
				names.append(item)
		return names
	except Exception as exc:
		logger.warning("Could not list Ollama models: %s", exc)
		return []


def pick_best_ollama_model(
	models: Sequence[str],
	priority: Sequence[str] = DEFAULT_PRIORITY,
) -> Optional[str]:
	"""Prefer coding-capable models from ``priority``, else first available."""
	if not models:
		return None
	lower_map = [(m, m.lower()) for m in models]
	for pref in priority:
		pref_l = pref.lower()
		for original, lowered in lower_map:
			if pref_l in lowered:
				return original
	return models[0]


def resolve_ollama_model(
	requested: Optional[str] = None,
	*,
	base_url: str = OLLAMA_API,
	print_fn=print,
) -> Optional[str]:
	"""Resolve an installed Ollama model name (without ``ollama/`` prefix).

	``requested`` may be ``None`` / ``\"auto\"`` to auto-pick, or a substring
	of an installed model name. Returns ``None`` and prints guidance on failure.
	Never prints API keys or .env contents.
	"""
	try:
		if not is_ollama_running(base_url=base_url):
			print_fn("Ollama is not running. Start it with: ollama serve")
			return None

		models = list_ollama_models(base_url=base_url)
		if not models:
			print_fn("No Ollama models installed. Run: ollama pull llama3")
			return None

		req = (requested or "auto").strip()
		if not req or req.lower() == "auto":
			best = pick_best_ollama_model(models)
			print_fn(f"Using Ollama model: {best}")
			return best

		match = next((m for m in models if req.lower() in m.lower()), None)
		if not match:
			print_fn(
				f"Model '{req}' not found in Ollama. Available: {', '.join(models)}"
			)
			return None
		print_fn(f"Using Ollama model: {match}")
		return match
	except Exception as exc:
		logger.error("Failed to resolve Ollama model: %s", exc)
		print_fn(f"Failed to resolve Ollama model: {exc}")
		return None


def litellm_ollama_id(model_name: str) -> str:
	"""Return a liteLLM-compatible Ollama model id."""
	name = (model_name or "").strip()
	if name.startswith("ollama/"):
		return name
	return f"ollama/{name}"
