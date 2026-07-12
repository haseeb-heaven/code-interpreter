"""Shared LLM helper for ReAct agent actions."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import litellm

from libs.free_llms import (
	FreeLLMCatalog,
	FreeModelsExhaustedError,
	format_free_models_exhausted_message,
	free_fallback_candidates,
	is_free_routing_failure,
	load_model_config,
	match_catalog_entry,
)

logger = logging.getLogger(__name__)

_DEFAULT_OPENROUTER_BASE = "https://openrouter.ai/api/v1"


def _ensure_dotenv_loaded() -> None:
	"""Best-effort load of repo ``.env`` without overriding existing env vars."""
	try:
		from dotenv import load_dotenv

		load_dotenv(override=False)
	except Exception:
		pass


def _candidate_from_model(
	model_name: str,
	*,
	configs_dir: str = "configs",
	catalog: Optional[FreeLLMCatalog] = None,
) -> Dict[str, Any]:
	"""Build a completion candidate dict for the primary model name."""
	catalog = catalog or FreeLLMCatalog.load()
	entry = match_catalog_entry(model_name, catalog, configs_dir=configs_dir)
	cfg: Dict[str, Any] = {}
	config_name = ""
	if entry is not None:
		config_name = entry.config
		cfg = load_model_config(entry.config, configs_dir=configs_dir) or {}
	else:
		maybe = load_model_config(model_name, configs_dir=configs_dir)
		if maybe:
			cfg = maybe
			config_name = model_name

	model_id = str(cfg.get("model") or model_name).strip()
	provider = str(cfg.get("provider") or (entry.provider if entry else "")).strip()
	api_base = str(cfg["api_base"]).strip() if cfg.get("api_base") else None
	if not api_base and (
		provider.lower() == "openrouter"
		or model_id.lower().startswith("openrouter/")
		or "openrouter" in model_name.lower()
	):
		api_base = _DEFAULT_OPENROUTER_BASE
		provider = provider or "openrouter"

	return {
		"config": config_name or model_name,
		"model": model_id,
		"provider": provider,
		"api_base": api_base,
		"temperature": cfg.get("temperature", 0.1),
		"max_tokens": cfg.get("max_tokens", 4096),
	}


def _build_kwargs(
	candidate: Dict[str, Any],
	messages: List[Dict[str, str]],
	api_key: Optional[str],
) -> Dict[str, Any]:
	"""Build litellm.completion kwargs for one candidate."""
	model = str(candidate["model"])
	provider = str(candidate.get("provider") or "").strip().lower()
	api_base = candidate.get("api_base")

	kwargs: Dict[str, Any] = {
		"model": model,
		"messages": messages,
		"temperature": float(candidate.get("temperature") or 0.1),
		"max_tokens": int(candidate.get("max_tokens") or 4096),
	}

	if provider == "openrouter" or (api_base and "openrouter.ai" in str(api_base)):
		_ensure_dotenv_loaded()
		key = api_key or os.getenv("OPENROUTER_API_KEY")
		if key:
			kwargs["api_key"] = key
		kwargs["api_base"] = api_base or _DEFAULT_OPENROUTER_BASE
		kwargs["custom_llm_provider"] = "openai"
		kwargs["extra_headers"] = {
			"HTTP-Referer": "https://github.com/haseeb-heaven/code-interpreter",
			"X-OpenRouter-Title": "Code Interpreter",
		}
		return kwargs

	if api_key:
		kwargs["api_key"] = api_key
	if api_base:
		kwargs["api_base"] = api_base
		kwargs["custom_llm_provider"] = "openai"
	return kwargs


def _extract_content_and_metrics(response: Any) -> Tuple[str, Dict[str, Any]]:
	content = ""
	try:
		content = response.choices[0].message.content or ""
	except Exception:
		if isinstance(response, dict):
			content = (
				((response.get("choices") or [{}])[0].get("message") or {}).get("content")
				or ""
			)
	try:
		cost = float(litellm.completion_cost(completion_response=response) or 0.0)
	except Exception:
		cost = 0.0
	tokens = 0
	try:
		usage = getattr(response, "usage", None)
		if usage is not None:
			tokens = int(getattr(usage, "total_tokens", 0) or 0)
		elif isinstance(response, dict) and response.get("usage"):
			tokens = int(response["usage"].get("total_tokens") or 0)
	except Exception:
		tokens = 0
	return content, {"cost": cost, "tokens": tokens}


def call_llm(
	model_name: str,
	messages: List[Dict[str, str]],
	api_key: Optional[str] = None,
	*,
	enable_free_fallback: bool = True,
	configs_dir: str = "configs",
	catalog: Optional[FreeLLMCatalog] = None,
	on_fallback: Optional[Any] = None,
) -> Tuple[str, Dict[str, Any]]:
	"""Call litellm and return (content, metrics).

	On free-router failures (502 / Invalid URL / Stealth, etc.), automatically
	tries the next available free catalog model when ``enable_free_fallback``.

	Metrics include cost/tokens plus optional ``model_used`` / ``fallback_used``.
	"""
	cat = catalog or FreeLLMCatalog.load()
	primary = _candidate_from_model(model_name, configs_dir=configs_dir, catalog=cat)
	candidates: List[Dict[str, Any]] = [primary]
	if enable_free_fallback:
		seed = str(primary.get("config") or primary["model"])
		candidates.extend(
			free_fallback_candidates(
				seed,
				catalog=cat,
				environ=dict(os.environ),
				configs_dir=configs_dir,
			)
		)

	seen_models: set[str] = set()
	unique: List[Dict[str, Any]] = []
	for candidate in candidates:
		mid = str(candidate.get("model") or "").strip().lower()
		if not mid or mid in seen_models:
			continue
		seen_models.add(mid)
		unique.append(candidate)
	candidates = unique

	tried: List[str] = []
	last_exc: Optional[BaseException] = None

	for index, candidate in enumerate(candidates):
		label = str(candidate.get("config") or candidate.get("model") or "?")
		model_id = str(candidate["model"])
		tried.append(f"{label} ({model_id})" if label != model_id else model_id)
		try:
			kwargs = _build_kwargs(candidate, messages, api_key)
			response = litellm.completion(**kwargs)
			content, metrics = _extract_content_and_metrics(response)
			metrics = dict(metrics)
			metrics["model_used"] = model_id
			metrics["fallback_used"] = 1.0 if index > 0 else 0.0
			if index > 0:
				logger.warning(
					"Free model fallback succeeded: %s -> %s (%s)",
					model_name,
					label,
					model_id,
				)
				if callable(on_fallback):
					try:
						on_fallback(candidate)
					except Exception as hook_exc:
						logger.debug("on_fallback hook failed: %s", hook_exc)
			return content, metrics
		except Exception as exc:
			last_exc = exc
			if enable_free_fallback and is_free_routing_failure(exc) and index < len(candidates) - 1:
				logger.warning(
					"Free model %s failed (%s); trying next free preset…",
					tried[-1],
					exc,
				)
				continue
			if enable_free_fallback and is_free_routing_failure(exc):
				break
			logger.error("LLM call failed: %s", exc)
			raise

	message = format_free_models_exhausted_message(tried, last_exc)
	logger.error(message)
	raise FreeModelsExhaustedError(message, tried=tried, last_error=last_exc) from last_exc
