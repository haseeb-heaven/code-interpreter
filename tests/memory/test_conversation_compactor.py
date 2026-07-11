"""Unit tests for conversation ContextManager compaction (#215)."""

from __future__ import annotations

import unittest

from libs.memory.context_manager import ContextManager


class TestContextManagerCompaction(unittest.TestCase):
	def test_no_compact_under_limit(self):
		mgr = ContextManager(token_limit=10_000, preserve_last_n=2)
		messages = [
			{"role": "system", "content": "sys"},
			{"role": "user", "content": "hello"},
			{"role": "assistant", "content": "hi"},
		]
		out = mgr.maybe_compact(messages)
		self.assertEqual(out, messages)

	def test_compacts_middle_with_summarizer(self):
		mgr = ContextManager(token_limit=10, preserve_last_n=2)
		messages = [
			{"role": "system", "content": "sys"},
			{"role": "user", "content": "aaaa " * 50},
			{"role": "assistant", "content": "bbbb " * 50},
			{"role": "user", "content": "cccc " * 50},
			{"role": "assistant", "content": "tail-1"},
			{"role": "user", "content": "tail-2"},
		]

		def summarize_fn(prompt: str) -> str:
			return "SUMMARY"

		out = mgr.maybe_compact(messages, summarize_fn=summarize_fn)
		self.assertEqual(out[0]["role"], "system")
		self.assertIn("[Context Summary]", out[1]["content"])
		self.assertIn("SUMMARY", out[1]["content"])
		self.assertEqual(out[-2]["content"], "tail-1")
		self.assertEqual(out[-1]["content"], "tail-2")


if __name__ == "__main__":
	unittest.main()
