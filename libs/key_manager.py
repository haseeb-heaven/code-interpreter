"""Multi-key pool, circuit breaker, and error classification for LLM providers."""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from libs.rate_limiter import TokenBucket


class CircuitState(str, Enum):
	CLOSED = "CLOSED"
	OPEN = "OPEN"
	HALF_OPEN = "HALF_OPEN"


class ErrorType(str, Enum):
	TRANSIENT = "TRANSIENT"
	QUOTA = "QUOTA"
	AUTH = "AUTH"
	FATAL = "FATAL"


class AllKeysExhaustedError(Exception):
	"""Raised when every key for a provider is unavailable."""


# Env var base names keyed by provider id used in KeyManager.
PROVIDER_ENV_MAP: Dict[str, str] = {
	"openai": "OPENAI_API_KEY",
	"gemini": "GEMINI_API_KEY",
	"anthropic": "ANTHROPIC_API_KEY",
	"groq": "GROQ_API_KEY",
	"deepseek": "DEEPSEEK_API_KEY",
	"huggingface": "HUGGINGFACE_API_KEY",
	"nvidia": "NVIDIA_API_KEY",
	"openrouter": "OPENROUTER_API_KEY",
	"z-ai": "Z_AI_API_KEY",
	"browser-use": "BROWSER_USE_API_KEY",
	"cerebras": "CEREBRAS_API_KEY",
}

# Map config/env key names → provider id
ENV_TO_PROVIDER: Dict[str, str] = {v: k for k, v in PROVIDER_ENV_MAP.items()}


def _now() -> float:
	return time.time()


@dataclass
class KeyState:
	"""State for a single API key in a provider pool."""

	value: str
	index: int
	failures: int = 0
	successes: int = 0
	rate_limited_until: float = 0.0
	circuit_state: CircuitState = CircuitState.CLOSED
	circuit_open_until: float = 0.0
	last_used: float = 0.0
	permanently_broken: bool = False
	circuit_threshold: int = 3
	circuit_cooldown: float = 120.0
	bucket: Optional[TokenBucket] = field(default=None, repr=False)

	def is_circuit_open(self, now: Optional[float] = None) -> bool:
		"""True when the circuit blocks use (OPEN and still in cooldown)."""
		now = _now() if now is None else now
		if self.circuit_state == CircuitState.CLOSED:
			return False
		if self.circuit_state == CircuitState.OPEN:
			if now >= self.circuit_open_until:
				# Cooldown elapsed → allow one probe
				self.circuit_state = CircuitState.HALF_OPEN
				return False
			return True
		# HALF_OPEN: probe allowed (not "open" for blocking purposes of is_circuit_open)
		return False

	def is_available(self, now: Optional[float] = None) -> bool:
		now = _now() if now is None else now
		if self.permanently_broken:
			return False
		if self.rate_limited_until > now:
			return False
		if self.circuit_state == CircuitState.OPEN and now < self.circuit_open_until:
			return False
		if self.circuit_state == CircuitState.OPEN and now >= self.circuit_open_until:
			self.circuit_state = CircuitState.HALF_OPEN
		return True

	def record_success(self) -> None:
		self.failures = 0
		self.successes += 1
		self.circuit_state = CircuitState.CLOSED
		self.circuit_open_until = 0.0
		self.rate_limited_until = 0.0
		self.last_used = _now()

	def record_failure(
		self,
		*,
		is_rate_limit: bool = False,
		is_quota: bool = False,
		is_auth: bool = False,
		rate_limit_seconds: float = 60.0,
		quota_seconds: float = 600.0,
	) -> None:
		now = _now()
		self.last_used = now
		if is_auth:
			self.permanently_broken = True
			self.circuit_state = CircuitState.OPEN
			self.circuit_open_until = now + self.circuit_cooldown
			return
		if is_quota:
			self.rate_limited_until = max(self.rate_limited_until, now + quota_seconds)
			self.failures += 1
		elif is_rate_limit:
			self.rate_limited_until = max(self.rate_limited_until, now + rate_limit_seconds)
			self.failures += 1
		else:
			self.failures += 1

		if self.circuit_state == CircuitState.HALF_OPEN:
			self.circuit_state = CircuitState.OPEN
			self.circuit_open_until = now + self.circuit_cooldown
			return

		if self.failures >= self.circuit_threshold:
			self.circuit_state = CircuitState.OPEN
			self.circuit_open_until = now + self.circuit_cooldown

	def mask(self) -> str:
		v = self.value or ""
		if len(v) <= 8:
			return "***"
		return f"{v[:3]}...{v[-3:]}"


class ProviderKeyPool:
	"""Thread-safe round-robin pool of keys for one provider."""

	def __init__(
		self,
		provider: str,
		keys: List[str],
		*,
		circuit_threshold: int = 3,
		circuit_cooldown: float = 120.0,
		rpm: float = 60.0,
		burst: int = 10,
	):
		if not keys:
			raise ValueError("ProviderKeyPool requires at least one key")
		self.provider = provider
		self._lock = threading.Lock()
		self._cursor = 0
		self._keys: List[KeyState] = []
		for i, raw in enumerate(keys):
			bucket = TokenBucket(capacity=float(burst), refill_rate=float(rpm) / 60.0)
			self._keys.append(
				KeyState(
					value=raw,
					index=i,
					circuit_threshold=circuit_threshold,
					circuit_cooldown=circuit_cooldown,
					bucket=bucket,
				)
			)

	def get_key(self) -> Optional[KeyState]:
		with self._lock:
			n = len(self._keys)
			for _ in range(n):
				ks = self._keys[self._cursor % n]
				self._cursor = (self._cursor + 1) % n
				if ks.is_available():
					ks.last_used = _now()
					return ks
			return None

	def record_success(self, key_index: int) -> None:
		with self._lock:
			if 0 <= key_index < len(self._keys):
				self._keys[key_index].record_success()

	def record_failure(self, key_index: int, **kwargs) -> None:
		with self._lock:
			if 0 <= key_index < len(self._keys):
				self._keys[key_index].record_failure(**kwargs)

	def available_count(self) -> int:
		with self._lock:
			return sum(1 for k in self._keys if k.is_available())

	def earliest_recovery(self) -> float:
		with self._lock:
			now = _now()
			etas = []
			for k in self._keys:
				if k.permanently_broken:
					continue
				etas.append(max(k.rate_limited_until, k.circuit_open_until, now))
			return min(etas) if etas else now

	def status(self) -> List[Dict[str, Any]]:
		with self._lock:
			now = _now()
			rows = []
			for k in self._keys:
				# Trigger half-open transition if needed
				k.is_available(now)
				rows.append(
					{
						"index": k.index,
						"masked": k.mask(),
						"available": k.is_available(now),
						"failures": k.failures,
						"successes": k.successes,
						"circuit_state": k.circuit_state.value,
						"rate_limited_until": k.rate_limited_until,
						"circuit_open_until": k.circuit_open_until,
						"permanently_broken": k.permanently_broken,
					}
				)
			return rows

	@property
	def size(self) -> int:
		return len(self._keys)

	def keys(self) -> List[KeyState]:
		return list(self._keys)


class ErrorClassifier:
	"""Classify LLM exceptions into TRANSIENT / QUOTA / AUTH / FATAL."""

	@staticmethod
	def classify(error: Any) -> ErrorType:
		text = str(error or "").lower()
		# AUTH first
		auth_markers = [
			"401",
			"403",
			"invalid api key",
			"incorrect api key",
			"authentication",
			"unauthorized",
			"permission denied",
			"invalid_api_key",
		]
		if any(m in text for m in auth_markers):
			return ErrorType.AUTH

		quota_markers = [
			"quota",
			"credits",
			"billing",
			"insufficient_quota",
			"requires more credits",
			"payment required",
			"402",
		]
		if any(m in text for m in quota_markers):
			return ErrorType.QUOTA

		fatal_markers = [
			"model_not_found",
			"model not found",
			"invalid prompt",
			"bad request",
			"400",
			"does not exist",
			"unsupported",
		]
		if any(m in text for m in fatal_markers):
			return ErrorType.FATAL

		transient_markers = [
			"429",
			"rate limit",
			"ratelimit",
			"503",
			"502",
			"timeout",
			"timed out",
			"connection reset",
			"connection error",
			"overloaded",
			"temporarily unavailable",
			"resource_exhausted",
		]
		if any(m in text for m in transient_markers):
			return ErrorType.TRANSIENT

		# Default: treat unknown as transient so retries can help
		return ErrorType.TRANSIENT


class MetricsLogger:
	"""Append-only JSONL metrics for LLM calls."""

	def __init__(self, path: str = "logs/metrics.jsonl"):
		self.path = path
		self._lock = threading.Lock()
		parent = os.path.dirname(path)
		if parent:
			os.makedirs(parent, exist_ok=True)

	def log(
		self,
		*,
		provider: str,
		key_index: int,
		latency_ms: float,
		success: bool,
		error_type: Optional[str] = None,
	) -> None:
		payload = {
			"timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
			"provider": provider,
			"key_index": key_index,
			"latency_ms": round(float(latency_ms), 3),
			"success": bool(success),
			"error_type": error_type,
		}
		with self._lock:
			with open(self.path, "a", encoding="utf-8") as fh:
				fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

	def summary(self) -> Dict[str, Any]:
		if not os.path.exists(self.path):
			return {"providers": {}, "total": 0}
		by_provider: Dict[str, Dict[str, Any]] = {}
		total = 0
		with open(self.path, "r", encoding="utf-8") as fh:
			for line in fh:
				line = line.strip()
				if not line:
					continue
				try:
					row = json.loads(line)
				except json.JSONDecodeError:
					continue
				total += 1
				prov = row.get("provider", "unknown")
				bucket = by_provider.setdefault(
					prov,
					{
						"requests": 0,
						"successes": 0,
						"latencies": [],
						"rate_limit_events": 0,
						"circuit_open_events": 0,
					},
				)
				bucket["requests"] += 1
				if row.get("success"):
					bucket["successes"] += 1
				bucket["latencies"].append(float(row.get("latency_ms") or 0))
				et = (row.get("error_type") or "").upper()
				if et == "TRANSIENT" and not row.get("success"):
					bucket["rate_limit_events"] += 1
				if et in ("AUTH",) and not row.get("success"):
					bucket["circuit_open_events"] += 1

		out: Dict[str, Any] = {"providers": {}, "total": total}
		for prov, data in by_provider.items():
			lats = sorted(data["latencies"])
			p95 = lats[int(0.95 * (len(lats) - 1))] if lats else 0.0
			avg = sum(lats) / len(lats) if lats else 0.0
			reqs = data["requests"]
			out["providers"][prov] = {
				"requests": reqs,
				"success_rate": (data["successes"] / reqs) if reqs else 0.0,
				"avg_latency_ms": avg,
				"p95_latency_ms": p95,
				"rate_limit_events": data["rate_limit_events"],
				"circuit_open_events": data["circuit_open_events"],
			}
		return out


class KeyManager:
	"""Singleton multi-provider key manager."""

	_instance: Optional["KeyManager"] = None
	_instance_lock = threading.Lock()

	def __new__(cls, *args, **kwargs):
		with cls._instance_lock:
			if cls._instance is None:
				cls._instance = super().__new__(cls)
				cls._instance._initialized = False
			return cls._instance

	def __init__(self, getenv_fn=None, config: Optional[Dict[str, Any]] = None):
		if getattr(self, "_initialized", False):
			# Allow callers to refresh getenv/config on the live singleton
			# (e.g. initialize_client after /key-status created an empty instance).
			if getenv_fn is not None:
				self._getenv = getenv_fn
			if config is not None:
				self._config = config
			return
		self._getenv = getenv_fn or os.getenv
		self._config = config or {}
		self._pools: Dict[str, ProviderKeyPool] = {}
		self._lock = threading.Lock()
		self.metrics = MetricsLogger()
		self.reload()
		self._initialized = True

	@classmethod
	def reset_singleton(cls) -> None:
		with cls._instance_lock:
			cls._instance = None

	def _discover_keys(self, env_base: str) -> List[str]:
		numbered: List[str] = []
		for i in range(1, 11):
			val = self._getenv(f"{env_base}_{i}")
			if val and str(val).strip():
				numbered.append(str(val).strip())
		if numbered:
			return numbered
		bare = self._getenv(env_base)
		if bare and str(bare).strip():
			return [str(bare).strip()]
		return []

	def _cb_settings(self, provider: str) -> Tuple[int, float, float, int]:
		cfg = self._config or {}
		cb = cfg.get("circuit_breaker") or {}
		rl = cfg.get("rate_limits") or {}

		def _as_int(raw, default: int) -> int:
			if raw is None or str(raw).strip() == "":
				return default
			try:
				return int(raw)
			except (TypeError, ValueError):
				return default

		def _as_float(raw, default: float) -> float:
			if raw is None or str(raw).strip() == "":
				return default
			try:
				return float(raw)
			except (TypeError, ValueError):
				return default

		# Prefer KeyManager getenv (tests inject mocks); ignore non-numeric junk.
		threshold = _as_int(self._getenv("CIRCUIT_BREAKER_THRESHOLD"), 0) or _as_int(
			cb.get("threshold"), 3
		)
		cooldown = _as_float(self._getenv("CIRCUIT_BREAKER_COOLDOWN_SECONDS"), 0.0) or _as_float(
			cb.get("cooldown_seconds"), 120.0
		)
		rpm = _as_float(self._getenv("RATE_LIMIT_RPM"), 0.0) or _as_float(rl.get("rpm"), 60.0)
		burst = _as_int(rl.get("burst"), 10)
		# Re-apply defaults when env was present but invalid (0 from failed parse path)
		if threshold <= 0:
			threshold = _as_int(cb.get("threshold"), 3)
		if cooldown <= 0:
			cooldown = _as_float(cb.get("cooldown_seconds"), 120.0)
		if rpm <= 0:
			rpm = _as_float(rl.get("rpm"), 60.0)
		if burst <= 0:
			burst = 10
		return threshold, cooldown, rpm, burst

	def reload(self, config: Optional[Dict[str, Any]] = None) -> None:
		if config is not None:
			self._config = config
		with self._lock:
			self._pools.clear()
			for provider, env_base in PROVIDER_ENV_MAP.items():
				keys = self._discover_keys(env_base)
				if not keys:
					continue
				threshold, cooldown, rpm, burst = self._cb_settings(provider)
				self._pools[provider] = ProviderKeyPool(
					provider,
					keys,
					circuit_threshold=threshold,
					circuit_cooldown=cooldown,
					rpm=rpm,
					burst=burst,
				)

	def _normalize_provider(self, provider: str) -> str:
		provider = (provider or "").strip()
		upper = provider.upper()
		if upper in ENV_TO_PROVIDER:
			return ENV_TO_PROVIDER[upper]
		lower = provider.lower()
		if lower in ENV_TO_PROVIDER:
			return ENV_TO_PROVIDER[lower]
		if upper.endswith("_API_KEY"):
			return ENV_TO_PROVIDER.get(upper, lower.replace("_api_key", ""))
		return lower

	def acquire_key(self, provider: str) -> Optional[KeyState]:
		provider = self._normalize_provider(provider)
		with self._lock:
			pool = self._pools.get(provider)
			if not pool:
				return None
			return pool.get_key()

	def record_success(self, provider: str, key_index: int) -> None:
		provider = self._normalize_provider(provider)
		with self._lock:
			pool = self._pools.get(provider)
			if pool:
				pool.record_success(key_index)

	def record_failure(self, provider: str, key_index: int, **kwargs) -> None:
		provider = self._normalize_provider(provider)
		with self._lock:
			pool = self._pools.get(provider)
			if pool:
				pool.record_failure(key_index, **kwargs)

	def status(self) -> Dict[str, Any]:
		with self._lock:
			return {name: pool.status() for name, pool in self._pools.items()}

	def get_pool(self, provider: str) -> Optional[ProviderKeyPool]:
		return self._pools.get(self._normalize_provider(provider))

	def has_pool(self, provider: str) -> bool:
		return self.get_pool(provider) is not None

	def raise_if_exhausted(self, provider: str) -> None:
		"""Raise only when a pool exists and every key is unavailable.

		No pool (bare-env / tests without keys) is not exhaustion — callers
		should fall through to the normal single-key path.
		"""
		pool = self.get_pool(provider)
		if pool is None:
			return
		if pool.available_count() == 0:
			eta = pool.earliest_recovery()
			eta_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(eta))
			raise AllKeysExhaustedError(
				f"All keys exhausted for provider '{provider}'. Earliest recovery: {eta_str}"
			)


def provider_from_api_key_name(api_key_name: str) -> str:
	"""Map OPENAI_API_KEY → openai."""
	return ENV_TO_PROVIDER.get(api_key_name, api_key_name.lower().replace("_api_key", ""))


def resolve_search_provider(
	cli_provider: Optional[str] = None,
	cli_api_key: Optional[str] = None,
) -> tuple[str, Optional[str]]:
	"""
	Resolve web-search provider + API key (#217).

	Priority:
	1. Explicit CLI ``--search-provider`` / ``--search-api-key``
	2. ``TAVILY_API_KEY`` env → tavily
	3. ``SERPER_API_KEY`` env → serper
	4. duckduckgo (free, no key)
	"""
	cli_provider = (cli_provider or "").strip().lower() or None
	cli_api_key = (cli_api_key or "").strip() or None

	if cli_provider:
		if cli_provider in ("tavily", "serper"):
			key = cli_api_key
			if not key:
				env_name = "TAVILY_API_KEY" if cli_provider == "tavily" else "SERPER_API_KEY"
				key = os.getenv(env_name) or None
			return cli_provider, key
		return cli_provider, cli_api_key

	if cli_api_key:
		# Key without provider — prefer tavily if unspecified
		return "tavily", cli_api_key

	tavily = os.getenv("TAVILY_API_KEY")
	if tavily:
		return "tavily", tavily
	serper = os.getenv("SERPER_API_KEY")
	if serper:
		return "serper", serper
	return "duckduckgo", None
