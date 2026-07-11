"""Unit tests for memory entry + context window manager helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from libs.memory.memory_entry import MemoryEntry
from libs.memory.context_manager import ContextManager, ContextWindowManager


class TestMemoryEntry(unittest.TestCase):
	def test_to_from_dict_roundtrip(self):
		entry = MemoryEntry(
			role="user",
			content="hello",
			task="greet",
			tokens=2,
			tags=["code"],
		)
		data = entry.to_dict()
		restored = MemoryEntry.from_dict(data)
		self.assertEqual(restored.role, "user")
		self.assertEqual(restored.content, "hello")
		self.assertEqual(restored.task, "greet")
		self.assertEqual(restored.tokens, 2)
		self.assertEqual(restored.tags, ["code"])

	def test_defaults(self):
		entry = MemoryEntry(role="assistant", content="ok")
		self.assertEqual(entry.tokens, 0)
		self.assertTrue(entry.success)
		self.assertEqual(entry.tags, [])


class TestContextWindowManager(unittest.TestCase):
	def setUp(self):
		self.tmp = tempfile.TemporaryDirectory()
		self.history = str(Path(self.tmp.name) / "h.json")

	def tearDown(self):
		self.tmp.cleanup()

	def test_add_get_context_stats_clear(self):
		mgr = ContextWindowManager(max_tokens=1000, history_file=self.history)
		mgr.add(MemoryEntry(role="user", content="print hello world", task="hello"))
		mgr.add({"role": "assistant", "content": "hello", "task": "hello", "tokens": 1})
		ctx = mgr.get_context("hello", limit=2)
		self.assertGreaterEqual(len(ctx), 1)
		stats = mgr.stats()
		self.assertEqual(stats["entry_count"], 2)
		self.assertIn("total_tokens", stats)
		mgr.clear()
		self.assertEqual(mgr.stats()["entry_count"], 0)


class TestContextManagerCompact(unittest.TestCase):
	def test_passthrough_under_budget(self):
		cm = ContextManager(token_limit=100_000, preserve_last_n=2)
		messages = [{"role": "user", "content": "hi"}]
		self.assertEqual(cm.maybe_compact(messages), messages)

	def test_compacts_when_over_budget(self):
		cm = ContextManager(token_limit=10, preserve_last_n=2)
		messages = (
			[{"role": "system", "content": "sys"}]
			+ [{"role": "user", "content": f"msg-{i}-" + ("x" * 80)} for i in range(6)]
		)
		out = cm.maybe_compact(messages, summarize_fn=lambda p: "SUMMARY")
		self.assertTrue(any("[Context Summary]" in str(m.get("content", "")) for m in out))
		self.assertTrue(any(m.get("role") == "system" for m in out))


if __name__ == "__main__":
	unittest.main()
