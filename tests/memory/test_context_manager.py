import json
import os
import tempfile
import unittest

from libs.memory.context_manager import ContextWindowManager
from libs.memory.memory_entry import MemoryEntry


class TestContextWindowManager(unittest.TestCase):
	def _history_file(self, temp_dir, name="memory.json"):
		return os.path.join(temp_dir, name)

	def test_add_enforces_token_budget_by_dropping_oldest_entries(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			manager = ContextWindowManager(max_tokens=10, history_file=self._history_file(temp_dir))

			manager.add(MemoryEntry(role="user", content="first memory", task="alpha", tokens=4))
			manager.add(MemoryEntry(role="assistant", content="second memory", task="beta", tokens=4))
			manager.add(MemoryEntry(role="assistant", content="third memory is longer", task="gamma", tokens=6))

			context = manager.get_context("memory", limit=5)
			self.assertLessEqual(manager.stats()["total_tokens"], 10)
			self.assertEqual(manager.stats()["entry_count"], 2)
			self.assertNotIn("first memory", [entry["content"] for entry in context])
			self.assertIn("third memory is longer", [entry["content"] for entry in context])

	def test_get_context_returns_recent_and_relevant_entries(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			manager = ContextWindowManager(max_tokens=100, history_file=self._history_file(temp_dir))
			manager.add(MemoryEntry(role="assistant", content="Use pandas groupby for sales totals", task="dataframe aggregation", tokens=6))
			manager.add(MemoryEntry(role="assistant", content="Docker compose logs show a port conflict", task="debug docker", tokens=7))
			manager.add(MemoryEntry(role="assistant", content="Write pytest coverage for parser", task="parser tests", tokens=6))

			context = manager.get_context("pandas sales chart", limit=2)
			contents = [entry["content"] for entry in context]

			self.assertIn("Use pandas groupby for sales totals", contents)
			self.assertIn("Write pytest coverage for parser", contents)
			self.assertNotIn("Docker compose logs show a port conflict", contents)

	def test_clear_removes_entries_and_persists_empty_file(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			history_file = self._history_file(temp_dir)
			manager = ContextWindowManager(max_tokens=100, history_file=history_file)
			manager.add(MemoryEntry(role="user", content="remember this", task="clear test", tokens=2))

			manager.clear()
			reloaded = ContextWindowManager(max_tokens=100, history_file=history_file)

			self.assertEqual(manager.get_context("remember"), [])
			self.assertEqual(reloaded.stats()["entry_count"], 0)

	def test_stats_reports_counts_budget_and_history_file(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			history_file = self._history_file(temp_dir)
			manager = ContextWindowManager(max_tokens=50, history_file=history_file)
			manager.add(MemoryEntry(role="assistant", content="alpha beta gamma", task="stats", tokens=3))

			self.assertEqual(
				manager.stats(),
				{
					"entry_count": 1,
					"total_tokens": 3,
					"max_tokens": 50,
					"history_file": history_file,
				},
			)

	def test_history_file_without_directory_is_saved(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			cwd = os.getcwd()
			try:
				os.chdir(temp_dir)
				manager = ContextWindowManager(max_tokens=50, history_file="history.json")
				manager.add(MemoryEntry(role="assistant", content="local history file", task="save", tokens=3))

				self.assertTrue(os.path.exists("history.json"))
				self.assertEqual(ContextWindowManager(history_file="history.json").stats()["entry_count"], 1)
			finally:
				os.chdir(cwd)

	def test_loads_legacy_history_entries_from_shared_history_file(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			history_file = self._history_file(temp_dir)
			with open(history_file, "w", encoding="utf-8") as file:
				json.dump(
					[
						{
							"assistant": {"task": "legacy pandas task", "mode": "code"},
							"user": "build a pandas summary",
							"system": {"code": "print('legacy')", "output": "legacy pandas output"},
						}
					],
					file,
				)

			manager = ContextWindowManager(max_tokens=100, history_file=history_file)
			context = manager.get_context("pandas output", limit=1)

			self.assertEqual(manager.stats()["entry_count"], 1)
			self.assertEqual(context[0]["task"], "legacy pandas task")
			self.assertEqual(context[0]["content"], "legacy pandas output")


if __name__ == "__main__":
	unittest.main()
