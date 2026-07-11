"""SessionStore save/load round-trip tests (#226)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from libs.memory.session_store import SessionStore


class TestSessionRoundTrip(unittest.TestCase):
	def test_save_creates_json_file(self):
		with tempfile.TemporaryDirectory() as tmp:
			sm = SessionStore(session_id="test_session", session_dir=Path(tmp))
			fake_history = [
				{"role": "user", "content": "hello"},
				{"role": "assistant", "content": "hi there"},
			]
			sm.save(fake_history, model="gpt-4o")
			saved = Path(tmp) / "test_session.json"
			self.assertTrue(saved.exists())
			data = json.loads(saved.read_text(encoding="utf-8"))
			self.assertEqual(len(data["messages"]), 2)
			self.assertEqual(data["session_id"], "test_session")
			# No secrets in session payload
			raw = saved.read_text(encoding="utf-8").lower()
			self.assertNotIn("sk-", raw)
			self.assertNotIn("api_key", raw)

	def test_load_restores_history(self):
		with tempfile.TemporaryDirectory() as tmp:
			sm = SessionStore(session_id="roundtrip", session_dir=Path(tmp))
			original = [{"role": "user", "content": "test"}]
			sm.save(original, model="local-model")
			restored = sm.load()
			self.assertEqual(restored, original)

	def test_load_nonexistent_returns_empty(self):
		with tempfile.TemporaryDirectory() as tmp:
			sm = SessionStore(session_id="does_not_exist", session_dir=Path(tmp))
			self.assertEqual(sm.load(), [])

	def test_list_and_delete(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			a = SessionStore(session_id="a", session_dir=root)
			b = SessionStore(session_id="b", session_dir=root)
			a.save([{"role": "user", "content": "1"}], model="m")
			b.save([{"role": "user", "content": "2"}], model="m")
			listed = SessionStore.list_sessions(session_dir=root)
			ids = {s["session_id"] for s in listed}
			self.assertEqual(ids, {"a", "b"})
			self.assertTrue(SessionStore.delete_session("a", session_dir=root))
			self.assertFalse(a.exists())


if __name__ == "__main__":
	unittest.main()
