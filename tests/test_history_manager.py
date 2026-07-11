"""Unit tests for History JSON persistence helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from libs.history_manager import History


class TestHistoryManager(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.path = str(Path(self.tmp.name) / "history" / "history.json")
		self.history = History(self.path)

	def tearDown(self):
		self.tmp.cleanup()

	def test_creates_empty_file(self):
		self.assertTrue(Path(self.path).is_file())
		self.assertEqual(json.loads(Path(self.path).read_text(encoding="utf-8")), [])

	def test_save_and_get_chat_history(self):
		self.history.save_history_json(
			task="sum",
			mode="code",
			os_name="Windows",
			language="python",
			prompt="sum 1 to 10",
			code_snippet="print(55)",
			code_output="55",
			model_name="gpt-4o",
		)
		chat = self.history.get_chat_history(1)
		self.assertEqual(len(chat), 1)
		self.assertEqual(chat[0]["task"], "sum")
		self.assertEqual(chat[0]["output"], "55")

	def test_get_code_and_full_history(self):
		self.history.save_history_json(
			task="hello",
			mode="code",
			os_name="Linux",
			language="python",
			prompt="print hi",
			code_snippet="print('hi')",
			code_output="hi",
			model_name="local-model",
		)
		code = self.history.get_code_history(1)
		full = self.history.get_full_history(1)
		self.assertEqual(code[0]["code"], "print('hi')")
		self.assertEqual(full[0]["task"], "hello")
		self.assertEqual(full[0]["code"], "print('hi')")

	def test_empty_history_returns_empty_lists(self):
		self.assertEqual(self.history.get_chat_history(3), [])
		self.assertEqual(self.history._get_last_entries(2), [])

	def test_keeps_only_requested_count(self):
		for i in range(5):
			self.history.save_history_json(
				task=f"t{i}",
				mode="code",
				os_name="Windows",
				language="python",
				prompt=f"p{i}",
				code_snippet=f"print({i})",
				code_output=str(i),
				model_name="local-model",
			)
		chat = self.history.get_chat_history(2)
		self.assertEqual(len(chat), 2)
		self.assertEqual(chat[-1]["task"], "t4")

	def test_never_persists_api_key_secrets(self):
		self.history.save_history_json(
			task="sum",
			mode="code",
			os_name="Windows",
			language="python",
			prompt="sum numbers",
			code_snippet="print(1)",
			code_output="1",
			model_name="gpt-4o",
		)
		raw = Path(self.path).read_text(encoding="utf-8").lower()
		self.assertNotIn("sk-", raw)
		self.assertNotIn("api_key", raw)
		self.assertNotIn("openai_api_key", raw)


if __name__ == "__main__":
	unittest.main()
