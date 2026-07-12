"""Offline unit tests for live provider matrix harness (TDD).

Live execution is opt-in via LIVE_MATRIX=1 or SMOKE_LIVE=1 and is covered by
``scripts/run_provider_matrix.py`` plus ``TestLiveProviderMatrixOptIn``.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


class TestLooksReal(unittest.TestCase):
	def test_rejects_empty_short_and_placeholder(self):
		from tests.live.provider_detect import looks_real

		with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
			self.assertFalse(looks_real("OPENAI_API_KEY"))
		with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-short"}, clear=False):
			self.assertFalse(looks_real("OPENAI_API_KEY"))
		with patch.dict(
			os.environ,
			{"OPENAI_API_KEY": "sk-your_key_placeholder_here_xxx"},
			clear=False,
		):
			self.assertFalse(looks_real("OPENAI_API_KEY"))
		with patch.dict(
			os.environ,
			{"OPENAI_API_KEY": "sk-live-looking-key-1234567890abcdef"},
			clear=False,
		):
			self.assertTrue(looks_real("OPENAI_API_KEY"))

	def test_never_returns_secret_value(self):
		from tests.live.provider_detect import looks_real

		secret = "sk-super-secret-value-do-not-leak-12345"
		with patch.dict(os.environ, {"GROQ_API_KEY": secret}, clear=False):
			result = looks_real("GROQ_API_KEY")
		self.assertIsInstance(result, bool)
		self.assertNotIn(secret, str(result))


class TestDetectProviders(unittest.TestCase):
	def test_returns_presence_map_without_values(self):
		from tests.live.provider_detect import detect_providers

		env = {
			"OPENAI_API_KEY": "sk-live-looking-key-1234567890abcdef",
			"ANTHROPIC_API_KEY": "",
			"GROQ_API_KEY": "gsk_live_looking_key_1234567890",
			"GEMINI_API_KEY": "gemini-live-looking-key-123456",
			"OPENROUTER_API_KEY": "sk-or-v1-live-looking-key-1234567890",
			"HUGGINGFACE_API_KEY": "hf_live_looking_key_1234567890",
		}
		with patch.dict(os.environ, env, clear=False):
			rows = detect_providers()
		self.assertIsInstance(rows, list)
		self.assertTrue(rows)
		serialized = json.dumps(rows)
		for val in env.values():
			if val:
				self.assertNotIn(val, serialized)
		by_id = {r["id"]: r for r in rows}
		self.assertTrue(by_id["openai"]["available"])
		self.assertFalse(by_id["anthropic"]["available"])
		self.assertTrue(by_id["groq"]["available"])
		self.assertIn("config", by_id["openai"])
		self.assertIn("env_key", by_id["openai"])

	def test_includes_local_and_free_catalog_entries(self):
		from tests.live.provider_detect import detect_providers

		with patch(
			"tests.live.provider_detect.probe_local_endpoint",
			return_value=False,
		):
			rows = detect_providers()
		ids = {r["id"] for r in rows}
		self.assertIn("local", ids)
		self.assertTrue(
			any(r.get("tier") == "free" or "free" in r["id"] for r in rows)
			or any(r.get("source") == "free_catalog" for r in rows)
		)


class TestLanguageRuntimes(unittest.TestCase):
	def test_reports_python_javascript_r(self):
		from tests.live.provider_detect import language_runtimes

		rt = language_runtimes()
		self.assertIn("python", rt)
		self.assertIn("javascript", rt)
		self.assertIn("r", rt)
		for lang, info in rt.items():
			self.assertIn("available", info)
			self.assertIsInstance(info["available"], bool)


class TestBuildMatrixCases(unittest.TestCase):
	def test_covers_stream_sandbox_mode_language_axes(self):
		from tests.live.matrix_cases import build_matrix_cases

		fake_providers = [
			{
				"id": "openai",
				"config": "gpt-4o-mini",
				"env_key": "OPENAI_API_KEY",
				"available": True,
				"source": "family",
			},
			{
				"id": "groq",
				"config": "groq-llama-3.1-8b",
				"env_key": "GROQ_API_KEY",
				"available": True,
				"source": "family",
			},
			{
				"id": "local",
				"config": "local-model",
				"env_key": None,
				"available": False,
				"source": "local",
			},
		]
		runtimes = {
			"python": {"available": True},
			"javascript": {"available": True},
			"r": {"available": False},
		}
		cases = build_matrix_cases(fake_providers, runtimes)
		self.assertTrue(cases)
		kinds = {c["kind"] for c in cases}
		self.assertIn("llm_ping", kinds)
		self.assertIn("classic_smoke", kinds)
		self.assertIn("agentic_smoke", kinds)

		streams = {c.get("stream") for c in cases if c["kind"] == "llm_ping"}
		self.assertEqual(streams, {True, False})

		sandbox_vals = {c.get("sandbox") for c in cases if c["kind"] == "classic_smoke"}
		self.assertTrue({"on", "off"} <= sandbox_vals)

		langs = {c.get("language") for c in cases if c.get("language")}
		self.assertIn("python", langs)
		self.assertIn("javascript", langs)
		r_cases = [c for c in cases if c.get("language") == "r"]
		for c in r_cases:
			self.assertEqual(c.get("expected"), "skip")

		local_cases = [c for c in cases if c.get("provider") == "local"]
		for c in local_cases:
			self.assertEqual(c.get("expected"), "skip")


class TestClassifyOutcome(unittest.TestCase):
	def test_quota_is_skip_unexpected_is_fail(self):
		from tests.live.matrix_runner import classify_exception

		status, _ = classify_exception(RuntimeError("exceeded your current quota"))
		self.assertEqual(status, "SKIP")
		status, _ = classify_exception(RuntimeError("rate limit exceeded"))
		self.assertEqual(status, "SKIP")
		status, detail = classify_exception(RuntimeError("AttributeError: NoneType boom"))
		self.assertEqual(status, "FAIL")
		self.assertIn("AttributeError", detail)


class TestLlmPingDispatch(unittest.TestCase):
	def test_uses_dispatch_completion_not_run_completion(self):
		"""Regression: llm_ping must call libs.llm_dispatcher.dispatch_completion."""
		from unittest.mock import MagicMock, patch

		from tests.live.matrix_runner import _run_llm_ping

		fake_cfg = {"model": "gpt-4o-mini", "provider": "openai", "api_base": "None"}
		with patch("tests.live.matrix_runner._load_config", return_value=fake_cfg), patch(
			"libs.llm_dispatcher.dispatch_completion", return_value="PONG"
		) as mock_dispatch, patch.dict("sys.modules", {"litellm": MagicMock()}):
			status, detail = _run_llm_ping(
				{"config": "gpt-4o-mini", "stream": False}
			)
		self.assertEqual(status, "PASS")
		mock_dispatch.assert_called_once()
		self.assertIn("stream=False", detail)

	def test_empty_response_is_soft_skip(self):
		from unittest.mock import MagicMock, patch

		from tests.live.matrix_runner import _run_llm_ping

		fake_cfg = {"model": "gpt-4o-mini", "provider": "openai", "api_base": "None"}
		with patch("tests.live.matrix_runner._load_config", return_value=fake_cfg), patch(
			"libs.llm_dispatcher.dispatch_completion", return_value="   "
		), patch.dict("sys.modules", {"litellm": MagicMock()}):
			status, detail = _run_llm_ping({"config": "gpt-4o-mini", "stream": True})
		self.assertEqual(status, "SKIP")
		self.assertIn("empty", detail.lower())


class TestReportWriter(unittest.TestCase):
	def test_writes_markdown_and_json_under_report_dir(self):
		from tests.live.matrix_runner import write_report

		rows = [
			{"id": "a", "status": "PASS", "detail": "ok", "provider": "groq", "kind": "llm_ping"},
			{"id": "b", "status": "SKIP", "detail": "no key", "provider": "local", "kind": "llm_ping"},
		]
		with tempfile.TemporaryDirectory() as tmp:
			paths = write_report(rows, Path(tmp), run_id="unit")
			self.assertTrue(Path(paths["json"]).is_file())
			self.assertTrue(Path(paths["markdown"]).is_file())
			data = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
			self.assertEqual(data["summary"]["PASS"], 1)
			self.assertEqual(data["summary"]["SKIP"], 1)
			self.assertEqual(data["summary"]["FAIL"], 0)
			md = Path(paths["markdown"]).read_text(encoding="utf-8")
			self.assertIn("PASS", md)
			self.assertIn("groq", md)


@unittest.skipUnless(
	os.getenv("LIVE_MATRIX") == "1" or os.getenv("SMOKE_LIVE") == "1",
	"Set LIVE_MATRIX=1 (or SMOKE_LIVE=1) for live provider matrix",
)
class TestLiveProviderMatrixOptIn(unittest.TestCase):
	def test_live_matrix_no_hard_fails(self):
		from tests.live.matrix_runner import run_matrix

		with tempfile.TemporaryDirectory() as tmp:
			os.environ["INTERPRETER_TEST_DATA_DIR"] = tmp
			report_dir = Path(tmp) / "reports"
			result = run_matrix(report_dir=report_dir, python_exe=None)
			self.assertEqual(result["summary"]["FAIL"], 0, msg=json.dumps(result["summary"]))
			self.assertTrue(result["report_paths"]["json"])


if __name__ == "__main__":
	unittest.main()
