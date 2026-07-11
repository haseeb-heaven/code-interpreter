"""Unit tests for libs.core.prompt_builder.PromptBuilder."""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from libs.core.prompt_builder import PromptBuilder
from libs.core.session import SessionConfig
from libs.interpreter_lib import Interpreter


class TestPromptBuilder(unittest.TestCase):
	def _make_interp(self, mode="code", language="python", model="gpt-4o"):
		from tests.helpers.cli_args import make_interpreter_args

		with patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None), \
			 patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None):
			args = make_interpreter_args(mode=mode, model=model, lang=language)
			return Interpreter(args)

	def test_session_config_from_args(self):
		args = Namespace(
			lang="javascript", mode="chat", model="gpt-4o", save_code=True,
			exec=True, display_code=True, unsafe=True, history=True, file=None,
		)
		cfg = SessionConfig.from_args(args)
		self.assertEqual(cfg.language, "javascript")
		self.assertEqual(cfg.mode, "chat")
		self.assertTrue(cfg.execute_code)
		self.assertTrue(cfg.unsafe)

	def test_get_code_prompt_includes_task_and_os(self):
		interp = self._make_interp(mode="code")
		prompt = PromptBuilder(interp).get_code_prompt("print hello", "Linux")
		self.assertIn("print hello", prompt)
		self.assertIn("Linux", prompt)
		self.assertIn("python", prompt.lower())

	def test_get_mode_prompt_dispatches_code(self):
		interp = self._make_interp(mode="code")
		prompt = PromptBuilder(interp).build("list files", "Linux")
		self.assertIn("list files", prompt)

	def test_get_mode_prompt_dispatches_chat(self):
		interp = self._make_interp(mode="chat")
		prompt = PromptBuilder(interp).get_mode_prompt("what is 2+2?", "Linux")
		self.assertIn("what is 2+2?", prompt)

	def test_get_prompt_openai_style_roles(self):
		interp = self._make_interp(mode="code", model="gpt-4o")
		interp.INTERPRETER_MODEL = "gpt-4o"
		messages = PromptBuilder(interp).get_prompt("print 1", [])
		roles = [m["role"] for m in messages]
		self.assertEqual(roles, ["system", "assistant", "user"])

	def test_get_prompt_claude_uses_structured_user(self):
		interp = self._make_interp(mode="code", model="claude-3-sonnet")
		interp.INTERPRETER_MODEL = "claude-3-sonnet"
		messages = PromptBuilder(interp).get_prompt("print 1", [])
		self.assertEqual(len(messages), 1)
		self.assertEqual(messages[0]["role"], "user")
		self.assertIsInstance(messages[0]["content"], list)

	def test_script_prompt_forces_python_language(self):
		interp = self._make_interp(mode="script", language="javascript")
		PromptBuilder(interp).get_script_prompt("backup files", "Linux")
		self.assertEqual(interp.INTERPRETER_LANGUAGE, "python")

	def test_get_prompt_all_modes(self):
		for mode in ("code", "script", "command", "vision", "chat"):
			interp = self._make_interp(mode=mode)
			messages = PromptBuilder(interp).get_prompt("task", [{"role": "user", "content": "old"}])
			self.assertIsInstance(messages, list)
			self.assertGreaterEqual(len(messages), 1)

	def test_get_mode_prompt_script_command_vision(self):
		interp = self._make_interp(mode="script")
		self.assertIn("backup", PromptBuilder(interp).get_mode_prompt("backup", "Linux"))
		interp = self._make_interp(mode="command")
		self.assertIn("list files", PromptBuilder(interp).get_mode_prompt("list files", "Windows"))
		interp = self._make_interp(mode="vision")
		self.assertIn("image.png", PromptBuilder(interp).get_mode_prompt("image.png", "Linux"))

	def test_get_mode_prompt_unknown_returns_none(self):
		interp = self._make_interp(mode="code")
		interp.CODE_MODE = False
		interp.SCRIPT_MODE = False
		interp.COMMAND_MODE = False
		interp.VISION_MODE = False
		interp.CHAT_MODE = False
		self.assertIsNone(PromptBuilder(interp).get_mode_prompt("x", "Linux"))

	def test_get_code_prompt_normalizes_language(self):
		interp = self._make_interp(mode="code", language="ruby")
		PromptBuilder(interp).get_code_prompt("hello", "Linux")
		self.assertEqual(interp.INTERPRETER_LANGUAGE, "python")


if __name__ == "__main__":
	unittest.main()
