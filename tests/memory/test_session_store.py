"""Unit + CLI tests for persistent sessions (#218)."""

from __future__ import annotations

import io
import json
import tempfile
import time
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

from interpreter import _handle_session_mgmt_flags, build_parser, prepare_args
from libs.memory.session_store import SessionStore, sanitize_session_id


class TestSanitizeSessionId(unittest.TestCase):
	def test_accepts_safe_ids(self):
		self.assertEqual(sanitize_session_id("fastapi-project"), "fastapi-project")
		self.assertEqual(sanitize_session_id(" my_proj.1 "), "my_proj.1")

	def test_rejects_path_traversal(self):
		with self.assertRaises(ValueError):
			sanitize_session_id("../etc/passwd")
		with self.assertRaises(ValueError):
			sanitize_session_id("a/b")
		with self.assertRaises(ValueError):
			sanitize_session_id("")
		with self.assertRaises(ValueError):
			sanitize_session_id("..")


class TestSessionStore(unittest.TestCase):
	def setUp(self):
		self._tmpdir = tempfile.TemporaryDirectory()
		self.root = Path(self._tmpdir.name)

	def tearDown(self):
		self._tmpdir.cleanup()

	def test_save_and_load_roundtrip(self):
		store = SessionStore("demo", session_dir=self.root)
		messages = [
			{"role": "user", "content": "build an API"},
			{"role": "assistant", "content": "ok", "code": "print(1)"},
		]
		store.save(messages, model="local-model")
		self.assertTrue(store.exists())
		loaded = store.load()
		self.assertEqual(loaded, messages)
		meta = store.get_metadata()
		self.assertIsNotNone(meta)
		self.assertEqual(meta["session_id"], "demo")
		self.assertEqual(meta["message_count"], 2)
		self.assertEqual(meta["model"], "local-model")

	def test_load_missing_returns_empty(self):
		store = SessionStore("missing", session_dir=self.root)
		self.assertEqual(store.load(), [])
		self.assertIsNone(store.get_metadata())

	def test_save_skips_empty_messages(self):
		store = SessionStore("empty", session_dir=self.root)
		store.save([], model="x")
		self.assertFalse(store.exists())

	def test_clear_deletes_file(self):
		store = SessionStore("tmp", session_dir=self.root)
		store.save([{"role": "user", "content": "hi"}], model="m")
		store.clear()
		self.assertFalse(store.exists())
		self.assertEqual(store.load(), [])

	def test_corrupt_file_starts_fresh(self):
		store = SessionStore("bad", session_dir=self.root)
		store.path.write_text("{not-json", encoding="utf-8")
		self.assertEqual(store.load(), [])

	def test_messages_not_list_starts_fresh(self):
		store = SessionStore("nolist", session_dir=self.root)
		store.path.write_text(
			json.dumps({"session_id": "nolist", "messages": {"a": 1}}),
			encoding="utf-8",
		)
		self.assertEqual(store.load(), [])

	def test_list_sessions_sorted_by_updated(self):
		a = SessionStore("alpha", session_dir=self.root)
		b = SessionStore("beta", session_dir=self.root)
		a.save([{"n": 1}], model="m1")
		time.sleep(1.05)
		b.save([{"n": 1}, {"n": 2}], model="m2")
		listed = SessionStore.list_sessions(session_dir=self.root)
		self.assertEqual([s["session_id"] for s in listed], ["beta", "alpha"])
		self.assertEqual(listed[0]["message_count"], 2)

	def test_list_sessions_empty_dir(self):
		empty = self.root / "none"
		empty.mkdir()
		self.assertEqual(SessionStore.list_sessions(session_dir=empty), [])

	def test_delete_session(self):
		store = SessionStore("gone", session_dir=self.root)
		store.save([{"x": 1}], model="m")
		self.assertTrue(SessionStore.delete_session("gone", session_dir=self.root))
		self.assertFalse(store.exists())
		self.assertFalse(SessionStore.delete_session("gone", session_dir=self.root))

	def test_preserves_created_at_on_update(self):
		store = SessionStore("persist", session_dir=self.root)
		store.save([{"a": 1}], model="m")
		created = json.loads(store.path.read_text(encoding="utf-8"))["created_at"]
		time.sleep(1.05)
		store.save([{"a": 1}, {"b": 2}], model="m2")
		data = json.loads(store.path.read_text(encoding="utf-8"))
		self.assertEqual(data["created_at"], created)
		self.assertGreaterEqual(data["updated_at"], created)
		self.assertEqual(data["model"], "m2")


class TestSessionCliFlags(unittest.TestCase):
	def test_parser_session_flags(self):
		parser = build_parser()
		args = parser.parse_args(
			["--cli", "--session", "proj", "--new-session", "--list-sessions"]
		)
		self.assertEqual(args.session, "proj")
		self.assertTrue(args.new_session)
		self.assertTrue(args.list_sessions)

	def test_parser_delete_session(self):
		parser = build_parser()
		args = parser.parse_args(["--delete-session", "old-proj"])
		self.assertEqual(args.delete_session, "old-proj")

	def test_prepare_args_forces_cli_for_session(self):
		parser = build_parser()
		args = parser.parse_args(["--session", "demo", "-m", "local-model", "--mode", "code"])
		prepared = prepare_args(args, ["interpreter.py", "--session", "demo"])
		self.assertTrue(prepared.cli)

	def test_list_sessions_mgmt_flag(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			SessionStore("a", session_dir=root).save([{"x": 1}], model="m")
			buf = io.StringIO()
			args = Namespace(list_sessions=True, delete_session=None, new_session=False, session=None)
			with patch("libs.memory.session_store.SESSION_DIR", root), \
				patch("sys.stdout", buf):
				# list_sessions uses SESSION_DIR by default — patch class method
				with patch.object(SessionStore, "list_sessions", return_value=[
					{"session_id": "a", "message_count": 1, "model": "m", "updated_at": time.time()}
				]):
					self.assertTrue(_handle_session_mgmt_flags(args))
			self.assertIn("a", buf.getvalue())

	def test_delete_session_mgmt_flag(self):
		with tempfile.TemporaryDirectory() as tmp:
			root = Path(tmp)
			SessionStore("killme", session_dir=root).save([{"x": 1}], model="m")
			args = Namespace(
				list_sessions=False,
				delete_session="killme",
				new_session=False,
				session=None,
			)
			buf = io.StringIO()
			with patch("sys.stdout", buf), patch.object(
				SessionStore, "delete_session", return_value=True
			) as delete_mock:
				self.assertTrue(_handle_session_mgmt_flags(args))
				delete_mock.assert_called_once_with("killme")
			self.assertIn("deleted", buf.getvalue())

	def test_new_session_clears_and_continues(self):
		args = Namespace(
			list_sessions=False,
			delete_session=None,
			new_session=True,
			session="fresh",
		)
		buf = io.StringIO()
		with patch("sys.stdout", buf), patch.object(SessionStore, "clear") as clear_mock:
			# SessionStore(args.session).clear() constructs then clears
			with patch("libs.memory.session_store.SessionStore") as StoreCls:
				instance = StoreCls.return_value
				result = _handle_session_mgmt_flags(args)
				self.assertFalse(result)  # continue into REPL
				instance.clear.assert_called_once()
			self.assertIn("Cleared", buf.getvalue())


class TestInterpreterSessionHooks(unittest.TestCase):
	def test_record_session_turn_and_after_turn(self):
		from libs.interpreter_lib import Interpreter

		with tempfile.TemporaryDirectory() as tmp:
			store = SessionStore("hook", session_dir=Path(tmp))

			class FakeInterp:
				def _after_turn(self):
					Interpreter._after_turn(self)

			interp = FakeInterp()
			interp.session_store = store
			interp.conversation_history = []
			interp.INTERPRETER_MODE = "code"
			interp.INTERPRETER_LANGUAGE = "python"
			interp.INTERPRETER_MODEL = "local-model"
			Interpreter.record_session_turn(
				interp,
				task="print hi",
				prompt="print hi",
				code_snippet="print('hi')",
				code_output="hi\n",
				os_name="Windows",
			)
			self.assertEqual(len(interp.conversation_history), 1)
			loaded = store.load()
			self.assertEqual(len(loaded), 1)
			self.assertEqual(loaded[0]["assistant"]["task"], "print hi")

	def test_record_noop_without_session(self):
		from libs.interpreter_lib import Interpreter

		interp = MagicMock()
		interp.session_store = None
		interp.conversation_history = []
		Interpreter.record_session_turn(interp, task="x")
		self.assertEqual(interp.conversation_history, [])

	def test_handle_session_info_and_clear(self):
		from libs.interpreter_lib import Interpreter

		with tempfile.TemporaryDirectory() as tmp:
			store = SessionStore("cli", session_dir=Path(tmp))
			store.save([{"a": 1}], model="m")
			interp = MagicMock()
			interp.session_store = store
			interp.conversation_history = [{"a": 1}]
			interp.history = [{"a": 1}]
			interp.INTERPRETER_MODEL = "m"
			buf = io.StringIO()
			with patch("sys.stdout", buf):
				self.assertTrue(Interpreter.handle_session_command(interp, "/session info"))
				self.assertTrue(Interpreter.handle_session_command(interp, "/session clear"))
			self.assertEqual(interp.conversation_history, [])
			self.assertFalse(store.exists())

	def test_handle_sessions_list(self):
		from libs.interpreter_lib import Interpreter

		interp = MagicMock()
		interp.session_store = None
		buf = io.StringIO()
		with patch("sys.stdout", buf), patch.object(
			SessionStore, "list_sessions", return_value=[]
		):
			self.assertTrue(Interpreter.handle_session_command(interp, "/sessions"))
		self.assertIn("No saved sessions", buf.getvalue())


if __name__ == "__main__":
	unittest.main()
