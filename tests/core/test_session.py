"""Unit tests for SessionConfig / apply_mode_flags / bootstrap helpers."""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

from libs.core.session import (
	SessionConfig,
	apply_mode_flags,
	bootstrap_interpreter,
	initialize_mode_from_args,
	resolve_prompt_input_flags,
)


class TestSessionConfig(unittest.TestCase):
	def test_from_args_defaults(self):
		args = Namespace(lang=None, mode=None, model=None, save_code=False, exec=False,
		                 display_code=False, unsafe=False, history=False, file=None)
		cfg = SessionConfig.from_args(args)
		self.assertEqual(cfg.language, "python")
		self.assertEqual(cfg.mode, "code")
		self.assertEqual(cfg.max_context_tokens, 8000)

	def test_from_args_with_file(self):
		args = Namespace(
			lang="javascript", mode="script", model="gpt-4o", save_code=True,
			exec=True, display_code=True, unsafe=False, history=True, file="prompt.txt",
			max_context_tokens=4096,
		)
		cfg = SessionConfig.from_args(args)
		self.assertEqual(cfg.language, "javascript")
		self.assertEqual(cfg.mode, "script")
		self.assertEqual(cfg.prompt_file, "prompt.txt")
		self.assertEqual(cfg.max_context_tokens, 4096)


class TestModeFlags(unittest.TestCase):
	def test_apply_mode_flags_code(self):
		target = MagicMock()
		apply_mode_flags(target, "code")
		self.assertTrue(target.CODE_MODE)
		self.assertFalse(target.CHAT_MODE)

	def test_apply_mode_flags_generate_clears(self):
		target = MagicMock()
		apply_mode_flags(target, "generate")
		self.assertEqual(target.INTERPRETER_MODE, "generate")

	def test_initialize_mode_from_args(self):
		target = MagicMock()
		args = Namespace(mode="vision")
		initialize_mode_from_args(target, args)
		self.assertTrue(target.VISION_MODE)


class TestResolvePromptFlags(unittest.TestCase):
	def test_file_sets_prompt_file(self):
		args = Namespace(file="task.txt")
		file_flag, input_flag = resolve_prompt_input_flags(args)
		self.assertTrue(file_flag)
		self.assertFalse(input_flag)

	def test_no_file_sets_input(self):
		args = Namespace(file=None)
		file_flag, input_flag = resolve_prompt_input_flags(args)
		self.assertFalse(file_flag)
		self.assertTrue(input_flag)


class TestBootstrapInterpreter(unittest.TestCase):
	def test_bootstrap_sets_flags_and_formatter(self):
		interp = MagicMock()
		interp.args = Namespace(
			lang="python",
			save_code=False,
			exec=False,
			display_code=False,
			model="gpt-4o",
			mode="code",
			file=None,
			history=False,
			agent=False,
			yes=True,
			output_format="plain",
			no_color=False,
			search=False,
			stream=False,
			session=None,
			list_sessions=False,
			delete_session=None,
			new_session=False,
		)
		interp.initialize_client = MagicMock()
		interp.initialize_mode = MagicMock()
		interp.utility_manager = MagicMock()
		interp.logger = MagicMock()
		with patch("libs.core.session.load_system_message", return_value="sys"), \
		     patch("libs.output_formatter.sys.stdout") as stdout:
			stdout.isatty.return_value = True
			bootstrap_interpreter(interp)
		self.assertTrue(interp.AUTO_YES)
		self.assertFalse(interp.AGENT_MODE)
		self.assertEqual(interp.INTERPRETER_MODE, "code")
		self.assertIsNotNone(interp.output_formatter)


if __name__ == "__main__":
	unittest.main()
