"""Shared LLM helper for ReAct agent actions."""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import litellm

from libs.free_llms import (
	DEFAULT_RATE_LIMIT_RETRIES,
	DEFAULT_RETRY_AFTER_CAP_SECONDS,
	FreeLLMCatalog,
	FreeModelsExhaustedError,
	format_free_models_exhausted_message,
	free_fallback_candidates,
	is_daily_free_quota_exhausted,
	is_free_routing_failure,
	is_openrouter_free_candidate,
	is_rate_limit_failure,
	is_tool_use_unsupported,
	load_model_config,
	match_catalog_entry,
	parse_retry_after_seconds,
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
		# Prefer LiteLLM native OpenRouter routing (openrouter/<author>/<model>).
		# Avoid openai-shim model-ID validation that rejects *:free upstream ids.
		if not model.lower().startswith("openrouter/"):
			kwargs["model"] = f"openrouter/{model}"
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


def _sleep_for_rate_limit(exc: BaseException, *, sleep_fn=None) -> float:
	"""Sleep using parsed retry-after (capped). Returns seconds slept."""
	if sleep_fn is None:
		sleep_fn = time.sleep
	hint = parse_retry_after_seconds(exc, cap=DEFAULT_RETRY_AFTER_CAP_SECONDS)
	seconds = float(hint if hint is not None else 2.0)
	seconds = max(0.1, min(seconds, DEFAULT_RETRY_AFTER_CAP_SECONDS))
	logger.warning("Rate limited; sleeping %.1fs before retry…", seconds)
	sleep_fn(seconds)
	return seconds


def complete_with_free_fallback(
	model_name: str,
	messages: List[Dict[str, str]],
	api_key: Optional[str] = None,
	*,
	tools: Optional[List[Dict[str, Any]]] = None,
	tool_choice: Optional[str] = None,
	enable_free_fallback: bool = True,
	configs_dir: str = "configs",
	catalog: Optional[FreeLLMCatalog] = None,
	on_fallback: Optional[Any] = None,
	rate_limit_retries: int = DEFAULT_RATE_LIMIT_RETRIES,
	sleep_fn=None,
) -> Tuple[Any, Dict[str, Any]]:
	"""Call litellm with free-catalog fallback; return ``(raw_response, metrics)``.

	On free-router failures (502 / Invalid URL / Stealth, 429 rate limits,
	``free-models-per-day``, etc.), retries rate-limited models briefly (except
	daily free quota), skips remaining OpenRouter free after daily quota, then
	tries Groq / Gemini / HF / local catalog presets when ``enable_free_fallback``.
	"""
	if sleep_fn is None:
		sleep_fn = time.sleep
	# Ensure .env keys are visible before catalog availability filtering.
	_ensure_dotenv_loaded()
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
	max_same_retries = max(0, int(rate_limit_retries))
	skip_openrouter_free = False

	for index, candidate in enumerate(candidates):
		if skip_openrouter_free and is_openrouter_free_candidate(candidate):
			logger.warning(
				"Skipping OpenRouter free %s after daily free quota exhausted…",
				candidate.get("config") or candidate.get("model"),
			)
			continue

		label = str(candidate.get("config") or candidate.get("model") or "?")
		model_id = str(candidate["model"])
		tried.append(f"{label} ({model_id})" if label != model_id else model_id)
		same_retries = 0

		while True:
			try:
				kwargs = _build_kwargs(candidate, messages, api_key)
				if tools is not None:
					kwargs["tools"] = tools
					kwargs["tool_choice"] = tool_choice or "auto"
				response = litellm.completion(**kwargs)
				used_fallback = bool(index > 0 or (len(tried) > 1))
				metrics = {
					"model_used": model_id,
					"config_used": str(candidate.get("config") or model_id),
					"fallback_used": 1.0 if used_fallback else 0.0,
				}
				if used_fallback:
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
				return response, metrics
			except Exception as exc:
				last_exc = exc
				text_low = str(exc or "").lower()
				or_free = is_openrouter_free_candidate(candidate)
				provider_returned = "provider returned error" in text_low
				has_non_or_remaining = any(
					not is_openrouter_free_candidate(c) for c in candidates[index + 1 :]
				)
				tools_requested = tools is not None

				# Tool/function calling unsupported: skip remaining OR free immediately
				# when tools were requested (avoid hammering more :free routers).
				if (
					enable_free_fallback
					and tools_requested
					and is_tool_use_unsupported(exc)
				):
					if or_free and has_non_or_remaining:
						skip_openrouter_free = True
					logger.warning(
						"Tool use unsupported on %s; %s…",
						tried[-1],
						"skipping remaining OpenRouter free"
						if skip_openrouter_free
						else "trying next free preset",
					)
					break

				# Daily free quota: do not retry same OR free model; skip remaining OR free.
				if enable_free_fallback and is_daily_free_quota_exhausted(exc):
					skip_openrouter_free = True
					logger.warning(
						"Daily free quota exhausted on %s; skipping remaining OpenRouter free…",
						tried[-1],
					)
					break

				# Vague OR "Provider returned error" — jump to Groq/Gemini when available.
				if enable_free_fallback and or_free and provider_returned:
					if has_non_or_remaining:
						skip_openrouter_free = True
						logger.warning(
							"OpenRouter free provider error on %s; skipping remaining OpenRouter free…",
							tried[-1],
						)
					else:
						logger.warning(
							"OpenRouter free provider error on %s; trying next free preset…",
							tried[-1],
						)
					break

				# Rate-limit with an explicit retry-after: brief same-model retry.
				# Skip retries for OR free when the error has no wait hint (avoid burning slots).
				has_retry_hint = parse_retry_after_seconds(exc) is not None
				if (
					enable_free_fallback
					and is_rate_limit_failure(exc)
					and same_retries < max_same_retries
					and (has_retry_hint or not or_free)
				):
					same_retries += 1
					_sleep_for_rate_limit(exc, sleep_fn=sleep_fn)
					logger.warning(
						"Retrying %s after rate limit (%s/%s)…",
						tried[-1],
						same_retries,
						max_same_retries,
					)
					continue

				# OR free rate-limit / routing failure: skip remaining OR free when
				# Groq/Gemini/etc. are still in the candidate list.
				if enable_free_fallback and or_free and is_free_routing_failure(exc):
					if has_non_or_remaining:
						skip_openrouter_free = True
						logger.warning(
							"OpenRouter free %s failed (%s); skipping remaining OpenRouter free…",
							tried[-1],
							exc,
						)
					else:
						logger.warning(
							"Free model %s failed (%s); trying next free preset…",
							tried[-1],
							exc,
						)
					break

				if enable_free_fallback and is_free_routing_failure(exc) and index < len(candidates) - 1:
					logger.warning(
						"Free model %s failed (%s); trying next free preset…",
						tried[-1],
						exc,
					)
					break  # next candidate

				if enable_free_fallback and is_free_routing_failure(exc):
					# Last candidate exhausted
					break

				# With free fallback enabled, never surface a bare RateLimitError hard-stop.
				if enable_free_fallback and is_rate_limit_failure(exc):
					if or_free and has_non_or_remaining:
						skip_openrouter_free = True
					logger.warning(
						"Rate limit on %s; trying next free preset…",
						tried[-1],
					)
					break

				logger.error("LLM call failed: %s", exc)
				raise

	message = format_free_models_exhausted_message(tried, last_exc)
	logger.error(message)
	raise FreeModelsExhaustedError(message, tried=tried, last_error=last_exc) from last_exc


def call_llm(
	model_name: str,
	messages: List[Dict[str, str]],
	api_key: Optional[str] = None,
	*,
	enable_free_fallback: bool = True,
	configs_dir: str = "configs",
	catalog: Optional[FreeLLMCatalog] = None,
	on_fallback: Optional[Any] = None,
	rate_limit_retries: int = DEFAULT_RATE_LIMIT_RETRIES,
	sleep_fn=None,
) -> Tuple[str, Dict[str, Any]]:
	"""Call litellm and return (content, metrics).

	On free-router failures (502 / Invalid URL / Stealth, 429 rate limits, etc.),
	automatically retries rate-limited models briefly, then tries the next available
	free catalog model when ``enable_free_fallback``.

	Metrics include cost/tokens plus optional ``model_used`` / ``fallback_used``.
	"""
	response, metrics = complete_with_free_fallback(
		model_name,
		messages,
		api_key,
		enable_free_fallback=enable_free_fallback,
		configs_dir=configs_dir,
		catalog=catalog,
		on_fallback=on_fallback,
		rate_limit_retries=rate_limit_retries,
		sleep_fn=sleep_fn,
	)
	content, content_metrics = _extract_content_and_metrics(response)
	out = dict(metrics)
	out.update(content_metrics)
	out["model_used"] = metrics.get("model_used")
	out["fallback_used"] = metrics.get("fallback_used", 0.0)
	if metrics.get("config_used"):
		out["config_used"] = metrics["config_used"]
	return content, out
