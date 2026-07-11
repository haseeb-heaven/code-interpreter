# -*- coding: utf-8 -*-
"""Unit tests for Ollama helper (Issue #221) — mocked HTTP, no live server."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import MagicMock, patch

from libs.local.ollama_helper import (
	is_ollama_running,
	list_ollama_models,
	litellm_ollama_id,
	pick_best_ollama_model,
	resolve_ollama_model,
)


class _FakeResp:
	def __init__(self, payload, status=200):
		self._payload = payload
		self.status = status

	def read(self):
		return json.dumps(self._payload).encode("utf-8")

	def __enter__(self):
		return self

	def __exit__(self, *args):
		return False


class TestOllamaHelper(unittest.TestCase):
	def test_pick_best_prefers_codellama(self):
		self.assertEqual(
			pick_best_ollama_model(["mistral:latest", "codellama:7b", "llama3"]),
			"codellama:7b",
		)

	def test_pick_best_falls_back_to_first(self):
		self.assertEqual(pick_best_ollama_model(["custom-model"]), "custom-model")
		self.assertIsNone(pick_best_ollama_model([]))

	def test_litellm_id(self):
		self.assertEqual(litellm_ollama_id("llama3"), "ollama/llama3")
		self.assertEqual(litellm_ollama_id("ollama/llama3"), "ollama/llama3")

	@patch("libs.local.ollama_helper.urllib.request.urlopen")
	def test_is_ollama_running_true(self, mock_open):
		mock_open.return_value = _FakeResp({"models": []})
		self.assertTrue(is_ollama_running())

	@patch("libs.local.ollama_helper.urllib.request.urlopen", side_effect=OSError("down"))
	def test_is_ollama_running_false(self, _mock_open):
		self.assertFalse(is_ollama_running())

	@patch("libs.local.ollama_helper.urllib.request.urlopen")
	def test_list_models(self, mock_open):
		mock_open.return_value = _FakeResp(
			{"models": [{"name": "llama3:latest"}, {"name": "mistral"}]}
		)
		self.assertEqual(list_ollama_models(), ["llama3:latest", "mistral"])

	@patch("libs.local.ollama_helper.list_ollama_models", return_value=["llama3:8b", "mistral"])
	@patch("libs.local.ollama_helper.is_ollama_running", return_value=True)
	def test_resolve_auto(self, _run, _list):
		buf = io.StringIO()
		name = resolve_ollama_model("auto", print_fn=buf.write)
		self.assertEqual(name, "llama3:8b")
		self.assertIn("Using Ollama model", buf.getvalue())

	@patch("libs.local.ollama_helper.list_ollama_models", return_value=["llama3:8b"])
	@patch("libs.local.ollama_helper.is_ollama_running", return_value=True)
	def test_resolve_missing(self, _run, _list):
		buf = io.StringIO()
		name = resolve_ollama_model("nope", print_fn=buf.write)
		self.assertIsNone(name)
		self.assertIn("not found", buf.getvalue().lower())

	@patch("libs.local.ollama_helper.is_ollama_running", return_value=False)
	def test_resolve_not_running(self, _run):
		buf = io.StringIO()
		self.assertIsNone(resolve_ollama_model("auto", print_fn=buf.write))
		self.assertIn("not running", buf.getvalue().lower())


if __name__ == "__main__":
	unittest.main()
