"""Live smoke tests against real provider APIs (skipped when keys are absent).

Run:
  python -m unittest discover -s tests/smoke -v
  SMOKE_LIVE=1 python -m unittest discover -s tests/smoke -v

Or the matrix CLI:
  python scripts/smoke_all_models.py
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(".env"), override=True)

CONFIG_DIR = Path("configs")


def _expected_key_for_model(model: str, provider: str = "") -> str | None:
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


def _key_looks_real(key_name: str | None) -> bool:
	if key_name is None:
		return True  # local
	value = (os.getenv(key_name) or "").strip()
	if not value or len(value) < 16:
		return False
	low = value.lower()
	if any(tok in low for tok in ("your_", "changeme", "placeholder", "example", "xxx", "dummy")):
		return False
	if key_name == "OPENAI_API_KEY" and ("1234567890" in value or value == "sk-1234567890"):
		return False
	prefixes = {
		"OPENAI_API_KEY": "sk-",
		"ANTHROPIC_API_KEY": "sk-ant-",
		"GROQ_API_KEY": "gsk",
		"HUGGINGFACE_API_KEY": "hf_",
		"NVIDIA_API_KEY": "nvapi-",
		"OPENROUTER_API_KEY": "sk-or-v1-",
		"BROWSER_USE_API_KEY": "bu_",
	}
	prefix = prefixes.get(key_name)
	if prefix and not value.startswith(prefix):
		return False
	return True


def _one_config_per_key_family():
	"""Pick one representative config label per required API key (plus local)."""
	picked = {}
	for path in sorted(CONFIG_DIR.glob("*.json")):
		if path.name == "schema.json":
			continue
		data = json.loads(path.read_text())
		if "model" not in data:
			continue
		key = _expected_key_for_model(str(data.get("model", "")), str(data.get("provider", "")))
		family = key or "LOCAL"
		# Prefer free/openrouter-free and gpt-4o-mini / flash models when available
		prefer = (
			"openrouter-free" in path.stem
			or "flash" in path.stem
			or "mini" in path.stem
			or path.stem in ("local-model", "gpt-4o-mini", "groq-llama-3.1-8b", "deepseek-chat", "z-ai-glm-5")
		)
		if family not in picked or prefer:
			picked[family] = (path.stem, data)
	return picked


@unittest.skipUnless(os.getenv("SMOKE_LIVE") == "1", "Set SMOKE_LIVE=1 to hit live provider APIs")
class TestLiveModelSmoke(unittest.TestCase):
	def test_live_completion_per_key_family(self):
		import litellm
		from libs.llm_dispatcher import build_completion_kwargs

		litellm.set_verbose = False
		families = _one_config_per_key_family()
		self.assertTrue(families)

		failures = []
		skipped = []
		passed = []

		for family, (label, config) in sorted(families.items()):
			key = _expected_key_for_model(str(config.get("model", "")), str(config.get("provider", "")))
			if family == "LOCAL":
				skipped.append(f"{label}: local endpoint (covered by mock smoke)")
				continue
			if not _key_looks_real(key):
				skipped.append(f"{label}: missing/invalid {key}")
				continue
			model = str(config["model"])
			provider = str(config.get("provider", ""))
			api_base = str(config.get("api_base", "None"))
			try:
				kwargs = build_completion_kwargs(
					model=model,
					messages=[
						{"role": "system", "content": "Reply with exactly the word PONG and nothing else."},
						{"role": "user", "content": "ping"},
					],
					temperature=0,
					max_tokens=16,
					config_provider=provider,
					api_base=api_base,
				)
				# Avoid huge spend / slow reasoning models in smoke
				if any(x in model.lower() for x in ("o1", "o3", "o4", "reasoner", "opus")):
					skipped.append(f"{label}: skipped expensive/reasoning model in family smoke")
					continue
				response = litellm.completion(model=model, **kwargs)
				text = ""
				try:
					text = response.choices[0].message.content or ""
				except Exception:
					text = str(response)
				if not str(text).strip():
					failures.append(f"{label}: empty response")
				else:
					passed.append(f"{label}: ok ({len(str(text))} chars)")
			except Exception as exc:
				err = str(exc).lower()
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
					"resource_exhausted",
					"rate limit",
					"ratelimit",
					"too many requests",
					"provider returned error",
				)
				if any(m in err for m in skip_markers):
					skipped.append(f"{label}: {type(exc).__name__}: provider unavailable/quota/rate-limit")
				else:
					failures.append(f"{label}: {type(exc).__name__}: {exc}")

		report = "\nPASSED:\n  " + "\n  ".join(passed or ["(none)"])
		report += "\nSKIPPED:\n  " + "\n  ".join(skipped or ["(none)"])
		report += "\nFAILED:\n  " + "\n  ".join(failures or ["(none)"])
		print(report)
		self.assertFalse(failures, report)


if __name__ == "__main__":
	unittest.main()
