#!/usr/bin/env python3
"""Smoke-test matrix for every configs/models.toml model entry.

Offline (default): validate registry schema + key routing + initialize_client with fake keys.
Live: set SMOKE_LIVE=1 and provide real provider keys in .env / environment.

Usage:
  python scripts/smoke_all_models.py
  SMOKE_LIVE=1 python scripts/smoke_all_models.py
  SMOKE_LIVE=1 python scripts/smoke_all_models.py --only openrouter,groq,local
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
load_dotenv(ROOT / ".env", override=True)

from libs.core.model_registry import ModelRegistry  # noqa: E402

REGISTRY_PATH = ROOT / "configs" / "models.toml"


def expected_key(model: str, provider: str = "") -> str | None:
	model = (model or "").strip()
	provider = (provider or "").strip().lower()
	if "local" in model or "ollama" in model or provider in ("ollama", "local", "lmstudio"):
		return None
	if provider == "nvidia":
		return "NVIDIA_API_KEY"
	if provider in ("z-ai", "zai"):
		return "Z_AI_API_KEY"
	if provider in ("browser-use", "browser_use"):
		return "BROWSER_USE_API_KEY"
	if provider == "openrouter":
		return "OPENROUTER_API_KEY"
	if model.startswith("nvidia/"):
		return "NVIDIA_API_KEY"
	if model.startswith(("glm-", "z-ai/", "zai/")):
		return "Z_AI_API_KEY"
	if model.startswith(("bu-", "browser-use/")):
		return "BROWSER_USE_API_KEY"
	if model.startswith(("gpt", "o1", "o3", "o4")):
		return "OPENAI_API_KEY"
	if model.startswith("groq/") or "groq" in model:
		return "GROQ_API_KEY"
	if "claude" in model:
		return "ANTHROPIC_API_KEY"
	if "gemini" in model:
		return "GEMINI_API_KEY"
	if "deepseek" in model:
		return "DEEPSEEK_API_KEY"
	return "HUGGINGFACE_API_KEY"


def key_looks_real(key_name: str | None) -> bool:
	if key_name is None:
		return True
	value = (os.getenv(key_name) or "").strip()
	if not value or len(value) < 16:
		return False
	low = value.lower()
	if any(tok in low for tok in ("your_", "changeme", "placeholder", "example", "xxx", "dummy")):
		return False
	if key_name == "OPENAI_API_KEY" and "1234567890" in value:
		return False
	return True


def family_filter(only: set[str] | None, key: str | None, provider: str) -> bool:
	if not only:
		return True
	tokens = set()
	if key:
		tokens.add(key.replace("_API_KEY", "").lower().replace("_", "-"))
		tokens.add(key.lower())
	tokens.add((provider or "unknown").lower())
	if key is None:
		tokens.add("local")
	return bool(tokens & only)


def offline_row(label: str, config: dict) -> tuple[str, str]:
	from unittest.mock import MagicMock, patch
	from libs.interpreter_lib import Interpreter
	from libs.llm_dispatcher import build_completion_kwargs

	model = str(config["model"])
	provider = str(config.get("provider", ""))
	key = expected_key(model, provider)
	fake = {
		"OPENAI_API_KEY": "sk-unittest-openai-key-1234567890",
		"ANTHROPIC_API_KEY": "sk-ant-unittest-anthropic-key",
		"GEMINI_API_KEY": "gemini-unittest-key-123456",
		"GROQ_API_KEY": "gsk_unittest_groq_key_123456",
		"HUGGINGFACE_API_KEY": "hf_unittest_huggingface_key",
		"NVIDIA_API_KEY": "nvapi-unittest-nvidia-key",
		"DEEPSEEK_API_KEY": "deepseek-unittest-key-123",
		"Z_AI_API_KEY": "zai-unittest-key-12345",
		"OPENROUTER_API_KEY": "sk-or-v1-unittest-openrouter",
		"BROWSER_USE_API_KEY": "bu_unittest_browser_use_key",
	}
	env = {key: fake[key]} if key in fake else {}
	mock_um = MagicMock()
	mock_um.get_default_model_name.return_value = "gpt-4o"
	mock_um.read_config_file.return_value = dict(config)
	args = MagicMock(
		model=label, mode="code", lang="python", save_code=False, exec=False,
		display_code=False, history=False, unsafe=False, sandbox=True, file=None,
		tui=False, cli=True, agent=False, agentic=False,
	)
	with patch("libs.interpreter_lib.UtilityManager", return_value=mock_um), \
		patch("libs.interpreter_lib.load_dotenv"), \
		patch.dict(os.environ, env, clear=True):
		interp = Interpreter(args)
		assert interp.INTERPRETER_MODEL == model
		build_completion_kwargs(
			model=model,
			messages=[{"role": "user", "content": "ping"}],
			temperature=0.1,
			max_tokens=32,
			config_provider=provider,
			api_base=str(config.get("api_base", "None")),
		)
	return "PASS", f"offline ok -> key={key or 'LOCAL'}"


def live_row(label: str, config: dict) -> tuple[str, str]:
	import litellm
	from libs.llm_dispatcher import build_completion_kwargs

	litellm.set_verbose = False
	model = str(config["model"])
	provider = str(config.get("provider", ""))
	key = expected_key(model, provider)
	if key is None:
		return "SKIP", "local endpoint - use mock smoke"
	if not key_looks_real(key):
		return "SKIP", f"missing/invalid {key}"
	if any(x in model.lower() for x in ("o1", "o3", "reasoner", "opus-4", "gpt-5.4")) and "mini" not in model.lower() and "nano" not in model.lower():
		# Still allow free openrouter; skip expensive cloud models by default
		if provider != "openrouter" or ":free" not in model:
			if "free" not in label and "mini" not in label and "flash" not in label and "nano" not in label:
				return "SKIP", "expensive/reasoning model skipped in default live matrix"

	kwargs = build_completion_kwargs(
		model=model,
		messages=[
			{"role": "system", "content": "Reply with exactly PONG."},
			{"role": "user", "content": "ping"},
		],
		temperature=0,
		max_tokens=16,
		config_provider=provider,
		api_base=str(config.get("api_base", "None")),
	)
	try:
		response = litellm.completion(model=model, **kwargs)
	except Exception as exc:
		text = str(exc).lower()
		# Provider-side availability / billing / deprecation - not product regressions
		skip_markers = (
			"not found",
			"not a valid model",
			"unavailable for free",
			"deprecated",
			"not supported",
			"insufficient balance",
			"no resource package",
			"please recharge",
			"model_not_supported",
			"does not exist",
			"exceeded your current quota",
			"credit balance is too low",
			"billing details",
			"purchase credits",
		)
		if any(m in text for m in skip_markers):
			return "SKIP", f"{type(exc).__name__}: provider unavailable/deprecated"
		# Transient rate limits still count as FAIL for live matrix visibility
		raise
	text = ""
	try:
		text = response.choices[0].message.content or ""
	except Exception:
		text = str(response)
	if not str(text).strip():
		return "FAIL", "empty response"
	return "PASS", f"live ok ({len(str(text))} chars)"


def main() -> int:
	parser = argparse.ArgumentParser(description="Smoke matrix for all model registry entries")
	parser.add_argument("--only", default="", help="Comma filter: openai,anthropic,gemini,groq,openrouter,local,...")
	parser.add_argument("--live", action="store_true", help="Hit live APIs (or set SMOKE_LIVE=1)")
	args = parser.parse_args()
	live = args.live or os.getenv("SMOKE_LIVE") == "1"
	only = {x.strip().lower() for x in args.only.split(",") if x.strip()} or None

	registry = ModelRegistry.load(str(REGISTRY_PATH), use_cache=False)
	rows = []
	for label in registry.list_model_names():
		config = registry.get_model(label) or {}
		if "model" not in config:
			rows.append(("SKIP", label, "N/A", "not a model config"))
			print(f"[SKIP] {label:40} not a model config")
			continue
		key = expected_key(str(config.get("model", "")), str(config.get("provider", "")))
		provider = str(config.get("provider", "") or "unknown")
		if not family_filter(only, key, provider):
			continue
		try:
			status, detail = live_row(label, config) if live else offline_row(label, config)
		except Exception as exc:
			status, detail = "FAIL", f"{type(exc).__name__}: {exc}"
			if os.getenv("SMOKE_VERBOSE"):
				traceback.print_exc()
		rows.append((status, label, key or "LOCAL", detail))
		print(f"[{status:4}] {label:40} {detail}")

	counts = {k: sum(1 for r in rows if r[0] == k) for k in ("PASS", "SKIP", "FAIL")}
	print("\n=== SUMMARY ===")
	print(f"PASS={counts['PASS']} SKIP={counts['SKIP']} FAIL={counts['FAIL']} TOTAL={len(rows)}")
	print(f"mode={'LIVE' if live else 'OFFLINE'}")
	# Write machine-readable report
	out = ROOT / "logs" / "smoke_all_models.json"
	out.parent.mkdir(parents=True, exist_ok=True)
	out.write_text(json.dumps([
		{"status": s, "label": l, "key": k, "detail": d} for s, l, k, d in rows
	], indent=2))
	print(f"report: {out}")
	return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
	raise SystemExit(main())
