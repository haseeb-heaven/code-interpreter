"""Free / cheap LLM catalog for Gemini-CLI-style agentic runs.

Loads ``configs/free/catalog.json`` and helps pick models that work without
paid cloud lock-in (OpenRouter free, Groq/Gemini free tiers, Ollama, HF).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

logger = logging.getLogger(__name__)

DEFAULT_CATALOG_PATH = os.path.join("configs", "free", "catalog.json")

# Cap how long we wait on a single rate-limit "try again in Ns" hint.
DEFAULT_RETRY_AFTER_CAP_SECONDS = 60.0
# Same-model retries after a rate-limit before falling through to the next free preset.
DEFAULT_RATE_LIMIT_RETRIES = 2


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
		lines.append('Tip: python interpreter.py --free "describe your task here"')
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


# Markers for OpenRouter / free-router upstream failures that warrant model fallback.
_FREE_ROUTING_FAILURE_MARKERS = (
	"502",
	"503",
	"invalid url",
	"provider_name",
	'"stealth"',
	"stealth",
	"provider returned error",
	"no endpoints found",
	"temporarily unavailable",
	"overloaded",
	"all providers failed",
	"model is currently overloaded",
	"not a valid model id",
	"invalid model",
	"model_not_found",
	"no healthy upstream",
	"bad gateway",
	"deprecated",
	"notfounderror",
	"404",
	"no longer available",
	# Rate limits — retry same model briefly, then fall through to next free preset.
	"429",
	"rate_limit",
	"rate limit",
	"ratelimit",
	"rate_limit_exceeded",
	"too many requests",
	"tokens per minute",
	"tpm",
)

_RETRY_AFTER_PATTERNS = (
	re.compile(r"try again in\s+(\d+(?:\.\d+)?)\s*s", re.IGNORECASE),
	re.compile(r"retry[_-]after[:\s]+(\d+(?:\.\d+)?)", re.IGNORECASE),
	re.compile(r"retry_after_seconds[:\s=]+(\d+(?:\.\d+)?)", re.IGNORECASE),
	re.compile(r"Retry-After[:\s]+(\d+(?:\.\d+)?)", re.IGNORECASE),
	re.compile(r"please retry in\s+(\d+(?:\.\d+)?)\s*s", re.IGNORECASE),
	re.compile(r"wait\s+(\d+(?:\.\d+)?)\s*s(?:ec(?:ond)?s?)?", re.IGNORECASE),
)


class FreeModelsExhaustedError(RuntimeError):
	"""Raised when the primary free model and all catalog fallbacks fail."""

	def __init__(
		self,
		message: str,
		*,
		tried: Optional[Sequence[str]] = None,
		last_error: Optional[BaseException] = None,
	):
		super().__init__(message)
		self.tried = list(tried or [])
		self.last_error = last_error


def parse_retry_after_seconds(
	exc_or_text: Any,
	*,
	cap: float = DEFAULT_RETRY_AFTER_CAP_SECONDS,
) -> Optional[float]:
	"""Extract a sleep duration from rate-limit messages like \"try again in 2.5s\".

	Returns seconds capped at ``cap``, or None when no hint is found.
	"""
	text = str(exc_or_text or "")
	if not text:
		return None
	best: Optional[float] = None
	for pattern in _RETRY_AFTER_PATTERNS:
		for match in pattern.finditer(text):
			try:
				seconds = float(match.group(1))
			except (TypeError, ValueError):
				continue
			if seconds < 0:
				continue
			if best is None or seconds > best:
				best = seconds
	if best is None:
		return None
	if cap is not None and cap > 0:
		best = min(best, float(cap))
	return best


def is_rate_limit_failure(exc: BaseException) -> bool:
	"""True when the error is specifically a 429 / rate-limit (retryable)."""
	# LiteLLM / OpenAI exception class names often carry the signal even when
	# the message is a vague "Provider returned error".
	type_name = type(exc).__name__.lower()
	if "ratelimit" in type_name or type_name in {"rate_limit_error", "ratelimiterror"}:
		return True
	text = str(exc or "").lower()
	if not text:
		return False
	markers = (
		"429",
		"rate_limit",
		"rate limit",
		"ratelimit",
		"rate_limit_exceeded",
		"too many requests",
		"tokens per minute",
		"provider returned error",
	)
	return any(marker in text for marker in markers)


def is_free_routing_failure(exc: BaseException) -> bool:
	"""True when the error looks like a flaky free-router / upstream provider failure.

	Examples: OpenRouter 502 Invalid URL with provider Stealth, 503 overloaded,
	Groq/OpenRouter 429 rate limits, invalid/deprecated free model ids, etc.
	Auth / billing / missing-key errors are not treated as routing failures.
	"""
	text = str(exc or "").lower()
	if not text:
		return False
	# Rate limits are routing failures even if the message also mentions quota/TPM.
	if is_rate_limit_failure(exc):
		return True
	fatal = (
		"invalid api key",
		"incorrect api key",
		"authentication",
		"unauthorized",
		"401",
		"403",
		"credits",
		"billing",
		"payment required",
		"402",
		"not found in environment",
		"not found in .env",
	)
	# "quota" alone can appear in rate-limit messages; only treat as fatal
	# when it is not clearly a retryable rate limit.
	if any(marker in text for marker in fatal):
		return False
	if "quota" in text and not is_rate_limit_failure(exc):
		return False
	return any(marker in text for marker in _FREE_ROUTING_FAILURE_MARKERS)


def is_daily_free_quota_exhausted(exc: BaseException) -> bool:
	"""True when the error indicates the per-day free quota is used up.

	Matches 'free-models-per-day' or 'Remaining: 0' from OpenRouter.
	"""
	text = str(exc or "").lower()
	if not text:
		return False
	markers = (
		"free-models-per-day",
		"free models per day",
		"daily limit",
		"daily free quota",
		"remaining: 0",
		"remaining:0",
		"x-ratelimit-remaining: 0",
		"x-ratelimit-remaining:0",
		"quota exceeded",
		"daily quota",
	)
	return any(marker in text for marker in markers)


def is_openrouter_free_candidate(candidate: Dict[str, Any]) -> bool:
	"""True when *candidate* routes through OpenRouter free tier (:free suffix)."""
	model_id = str(candidate.get("model") or "").lower()
	provider = str(candidate.get("provider") or "").lower()
	api_base = str(candidate.get("api_base") or "").lower()
	if provider == "openrouter" or "openrouter.ai" in api_base:
		return True
	if model_id.startswith("openrouter/"):
		return True
	if ":free" in model_id:
		return True
	return False


def load_model_config(config_name: str, configs_dir: str = "configs") -> Optional[Dict[str, Any]]:
	"""Load ``configs/<config_name>.json``; return None if missing/invalid."""
	name = (config_name or "").strip()
	if not name:
		return None
	path = os.path.join(configs_dir, f"{name}.json")
	try:
		with open(path, "r", encoding="utf-8") as handle:
			payload = json.load(handle)
	except (OSError, json.JSONDecodeError) as exc:
		logger.debug("Could not load model config %s: %s", path, exc)
		return None
	return payload if isinstance(payload, dict) else None


def litellm_model_id(config: Dict[str, Any], fallback: str = "") -> str:
	"""Return the litellm/OpenRouter model id from a config dict."""
	return str(config.get("model") or fallback or "").strip()


def list_config_names(configs_dir: str = "configs") -> List[str]:
	"""Return sorted config basenames under ``configs_dir`` (excludes schema.json)."""
	try:
		names = [
			os.path.splitext(name)[0]
			for name in os.listdir(configs_dir)
			if name.endswith(".json") and name.lower() != "schema.json"
		]
		return sorted(names)
	except OSError as exc:
		logger.debug("Could not list configs in %s: %s", configs_dir, exc)
		return []


def resolve_model_config_name(
	name: str,
	*,
	configs_dir: str = "configs",
	catalog: Optional[FreeLLMCatalog] = None,
) -> Optional[str]:
	"""Map a user-facing model token to a ``configs/<name>.json`` basename.

	Accepts:
	- Config basename (``gemini-2.5-flash``)
	- Free-catalog id/config
	- LiteLLM model id when it uniquely matches one config (``gemini/gemini-2.5-pro``)

	Returns None when nothing resolves. Prefer config basenames in UX; do not
	treat litellm ids as primary names unless that mapping exists.
	"""
	needle = (name or "").strip()
	if not needle:
		return None

	direct_path = os.path.join(configs_dir, f"{needle}.json")
	if os.path.isfile(direct_path):
		return needle

	cat = catalog or FreeLLMCatalog.load()
	entry = cat.get(needle)
	if entry is not None and entry.config_exists(configs_dir):
		return entry.config

	needle_key = _normalize_key(needle)
	matches: List[str] = []
	for config_name in list_config_names(configs_dir):
		cfg = load_model_config(config_name, configs_dir=configs_dir)
		if not cfg:
			continue
		mid = _normalize_key(litellm_model_id(cfg, config_name))
		if mid and mid == needle_key:
			matches.append(config_name)
	if len(matches) == 1:
		return matches[0]
	return None


def _normalize_key(value: str) -> str:
	return (value or "").strip().lower()


def match_catalog_entry(
	model: str,
	catalog: FreeLLMCatalog,
	configs_dir: str = "configs",
) -> Optional[FreeModelEntry]:
	"""Match a litellm model id or config name to a free-catalog entry."""
	needle = _normalize_key(model)
	if not needle:
		return None

	direct = catalog.get(model)
	if direct is not None:
		return direct

	for entry in catalog.entries:
		cfg = load_model_config(entry.config, configs_dir=configs_dir)
		if not cfg:
			continue
		litellm_id = _normalize_key(litellm_model_id(cfg, entry.config))
		if litellm_id and litellm_id == needle:
			return entry
		if litellm_id.endswith("/" + needle) or needle.endswith("/" + litellm_id):
			return entry
	return None


def free_fallback_candidates(
	current_model: str,
	*,
	catalog: Optional[FreeLLMCatalog] = None,
	environ: Optional[Dict[str, str]] = None,
	configs_dir: str = "configs",
) -> List[Dict[str, Any]]:
	"""Ordered alternate free models to try after ``current_model`` fails.

	When the current model is OpenRouter-related, prefer Groq / Gemini / HF /
	local next (OR free-tier 429 / ``free-models-per-day`` / provider errors
	usually affect the whole OR free pool). Otherwise prefer same-provider
	siblings first, then other free catalog presets.
	"""
	cat = catalog or FreeLLMCatalog.load()
	current = (current_model or "").strip()
	current_key = _normalize_key(current)
	matched = match_catalog_entry(current, cat, configs_dir=configs_dir)

	available = cat.available(environ=environ, configs_dir=configs_dir, require_config_file=True)
	if not available:
		return []

	prefer_provider = (matched.provider if matched else "").strip().lower()
	if not prefer_provider and ("openrouter" in current_key or current_key.startswith("openrouter/")):
		prefer_provider = "openrouter"

	ordered: List[FreeModelEntry] = []
	seen_configs: set[str] = set()
	if prefer_provider == "openrouter":
		# Jump to Groq/Gemini/etc. before burning sibling OpenRouter :free slots.
		buckets = (
			[e for e in available if e.provider.lower() != "openrouter"],
			[e for e in available if e.provider.lower() == "openrouter"],
		)
	else:
		buckets = (
			[e for e in available if e.provider.lower() == prefer_provider] if prefer_provider else [],
			[e for e in available if not prefer_provider or e.provider.lower() != prefer_provider],
		)
	for bucket in buckets:
		for entry in bucket:
			if entry.config in seen_configs:
				continue
			seen_configs.add(entry.config)
			ordered.append(entry)

	candidates: List[Dict[str, Any]] = []
	for entry in ordered:
		if matched and entry.config == matched.config:
			continue
		cfg = load_model_config(entry.config, configs_dir=configs_dir) or {}
		model_id = litellm_model_id(cfg, entry.config)
		if not model_id:
			continue
		if _normalize_key(model_id) == current_key or _normalize_key(entry.config) == current_key:
			continue
		candidates.append(
			{
				"config": entry.config,
				"model": model_id,
				"provider": str(cfg.get("provider") or entry.provider or "").strip(),
				"api_base": (str(cfg["api_base"]).strip() if cfg.get("api_base") else None),
				"temperature": cfg.get("temperature", 0.1),
				"max_tokens": cfg.get("max_tokens", 4096),
			}
		)
	return candidates


def format_free_models_exhausted_message(
	tried: Sequence[str],
	last_error: Optional[BaseException] = None,
) -> str:
	"""User-facing message when every free model attempt failed."""
	tried_list = ", ".join(tried) if tried else "(none)"
	detail = ""
	if last_error is not None:
		raw = str(last_error).replace("\n", " ").strip()
		if len(raw) > 180:
			raw = raw[:177] + "..."
		detail = f" Last error: {raw}"
	return (
		f"All free / cheap models failed after trying: {tried_list}.{detail} "
		"Use /free to list presets or /model <name> to switch models."
	)
