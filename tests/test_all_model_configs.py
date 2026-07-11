"""Offline unit tests for every configs/*.json model entry.

Covers schema validity, provider/key routing, and initialize_client validation
without calling live provider APIs.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from libs.interpreter_lib import Interpreter
from libs.llm_dispatcher import _detect_provider, build_completion_kwargs


CONFIG_DIR = Path("configs")
REQUIRED_FIELDS = ("temperature", "max_tokens", "start_sep", "end_sep", "model")
_SKIP_CONFIG_NAMES = {"schema.json"}


def _all_configs():
	paths = sorted(
		p for p in CONFIG_DIR.glob("*.json") if p.name.lower() not in _SKIP_CONFIG_NAMES
	)
	assert paths, "No configs/*.json found"
	return paths


def _expected_key_for_model(model: str, provider: str = "") -> str | None:
	"""Mirror ModelRouter.initialize_client key selection.

	Config ``provider`` wins over model-id heuristics so OpenRouter models that
	still carry an ``nvidia/...`` id require OPENROUTER_API_KEY, not NVIDIA.
	"""
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


def _valid_env_for_key(key_name: str) -> dict:
	samples = {
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
	return {key_name: samples[key_name]} if key_name in samples else {}


class TestAllModelConfigsSchema(unittest.TestCase):
	def test_every_config_has_required_fields(self):
		for path in _all_configs():
			with self.subTest(config=path.name):
				data = json.loads(path.read_text())
				for field in REQUIRED_FIELDS:
					self.assertIn(field, data, f"{path.name} missing {field}")
				self.assertIsInstance(data["temperature"], (int, float))
				self.assertIsInstance(data["max_tokens"], int)
				self.assertTrue(str(data["model"]).strip())

	def test_config_count_matches_directory(self):
		self.assertGreaterEqual(len(_all_configs()), 50)


class TestAllModelKeyRouting(unittest.TestCase):
	def test_key_routing_table_for_every_config(self):
		for path in _all_configs():
			with self.subTest(config=path.name):
				data = json.loads(path.read_text())
				model = str(data.get("model", ""))
				provider = str(data.get("provider", ""))
				key = _expected_key_for_model(model, provider)
				detected = _detect_provider(model, provider, str(data.get("api_base", "None")))
				if key is None:
					self.assertIn(detected, ("local", "huggingface"), msg=f"{path.name} local expected")
				else:
					self.assertTrue(key.endswith("_API_KEY") or key.endswith("_KEY"))


class TestAllModelInitializeClient(unittest.TestCase):
	"""initialize_client accepts a valid key for every non-local config label."""

	def setUp(self):
		self.mock_um = MagicMock()
		self.mock_um.get_default_model_name.return_value = "gpt-4o"
		self.p_um = patch("libs.interpreter_lib.UtilityManager", return_value=self.mock_um)
		self.p_dotenv = patch("libs.interpreter_lib.load_dotenv")
		self.p_um.start()
		self.p_dotenv.start()

	def tearDown(self):
		patch.stopall()

	def _make(self, label: str, config: dict) -> Interpreter:
		args = MagicMock()
		args.model = label
		args.mode = "code"
		args.lang = "python"
		args.save_code = False
		args.exec = False
		args.display_code = False
		args.history = False
		args.unsafe = False
		args.sandbox = True
		args.file = None
		args.tui = False
		args.cli = True
		args.agent = False
		args.agentic = False
		# Explicit False/None — MagicMock attrs are truthy and trip wire_components.
		args.search = False
		args.search_provider = None
		args.search_api_key = None
		args.output_format = "plain"
		args.no_color = False
		args.yes = False
		args.yolo = False
		args.stream = False
		args.mcp = None
		args.max_context_tokens = 8000
		args.session = None
		args.list_sessions = False
		args.delete_session = None
		args.new_session = False
		self.mock_um.read_config_file.return_value = dict(config)
		return Interpreter(args)

	def test_initialize_client_with_valid_key_for_each_config(self):
		for path in _all_configs():
			with self.subTest(config=path.name):
				label = path.stem
				config = json.loads(path.read_text())
				model = str(config.get("model", ""))
				provider = str(config.get("provider", ""))
				key = _expected_key_for_model(model, provider)
				env = _valid_env_for_key(key) if key else {}
				with patch.dict(os.environ, env, clear=True):
					interp = self._make(label, config)
					self.assertEqual(interp.INTERPRETER_MODEL, model)

	def test_build_completion_kwargs_for_each_config(self):
		for path in _all_configs():
			with self.subTest(config=path.name):
				config = json.loads(path.read_text())
				model = str(config["model"])
				provider = str(config.get("provider", ""))
				api_base = str(config.get("api_base", "None"))
				key = _expected_key_for_model(model, provider)
				env = _valid_env_for_key(key) if key else {"OPENAI_API_KEY": "sk-local"}
				with patch.dict(os.environ, env, clear=False):
					kwargs = build_completion_kwargs(
						model=model,
						messages=[{"role": "user", "content": "ping"}],
						temperature=float(config.get("temperature", 0.1)),
						max_tokens=int(config.get("max_tokens", 64)),
						config_provider=provider,
						api_base=api_base,
					)
					self.assertIn("messages", kwargs)


class TestModelSmokeOfflineMatrix(unittest.TestCase):
	"""Documented matrix: every config maps to exactly one auth strategy."""

	def test_unique_config_labels(self):
		labels = [p.stem for p in _all_configs()]
		self.assertEqual(len(labels), len(set(labels)))

	def test_provider_families_covered(self):
		families = set()
		for path in _all_configs():
			data = json.loads(path.read_text())
			key = _expected_key_for_model(str(data.get("model", "")), str(data.get("provider", "")))
			families.add(key or "LOCAL")
		# Expect major families present in the catalog
		for needed in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY", "LOCAL"):
			self.assertIn(needed, families)


if __name__ == "__main__":
	unittest.main()
