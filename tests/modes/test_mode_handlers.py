"""Unit tests for mode handlers (code/chat/command/script/vision)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from libs.modes.chat_mode import ChatModeHandler
from libs.modes.code_mode import CodeModeHandler
from libs.modes.command_mode import CommandModeHandler
from libs.modes.script_mode import ScriptModeHandler
from libs.modes.vision_mode import VisionModeHandler


class TestCodeModeHandler(unittest.TestCase):
	def _handler(self, language="python"):
		interp = MagicMock()
		interp.CODE_MODE = True
		interp.INTERPRETER_LANGUAGE = language
		interp.prompt_builder = MagicMock()
		interp.prompt_builder.get_code_prompt.return_value = "CODE_PROMPT"
		return CodeModeHandler(interp), interp

	def test_exact_print_python(self):
		handler, _ = self._handler("python")
		out = handler.maybe_simplify_generated_code(
			"print exactly 'hello'",
			"print('something else')",
		)
		self.assertEqual(out, "print('hello')")

	def test_cwd_javascript(self):
		handler, _ = self._handler("javascript")
		out = handler.maybe_simplify_generated_code(
			"print the current working directory",
			"console.log('x')",
		)
		self.assertIn("process.cwd()", out)

	def test_directory_listing_python(self):
		handler, _ = self._handler("python")
		out = handler.maybe_simplify_generated_code(
			"list files in current directory",
			"print('nope')",
		)
		self.assertIn("os.listdir()", out)

	def test_disallowed_phrase_skips_listing_simplify(self):
		handler, _ = self._handler("python")
		original = "import os\nprint(os.listdir())\n# chart"
		out = handler.maybe_simplify_generated_code(
			"list files in current directory as chart",
			original,
		)
		self.assertEqual(out, original)

	def test_handle_delegates_to_prompt_builder(self):
		handler, interp = self._handler()
		result = handler.handle("task", {"os_name": "Windows"})
		self.assertEqual(result, "CODE_PROMPT")
		interp.prompt_builder.get_code_prompt.assert_called_once()


class TestOtherModeHandlers(unittest.TestCase):
	def test_chat_handle(self):
		interp = MagicMock()
		interp.prompt_builder.handle_chat_mode.return_value = "CHAT"
		self.assertEqual(ChatModeHandler(interp).handle("hi", {}), "CHAT")

	def test_vision_handle(self):
		interp = MagicMock()
		interp.prompt_builder.handle_vision_mode.return_value = "VISION"
		self.assertEqual(VisionModeHandler(interp).handle("img", {}), "VISION")

	def test_command_handle(self):
		interp = MagicMock()
		interp.prompt_builder.get_command_prompt.return_value = "CMD"
		self.assertEqual(
			CommandModeHandler(interp).handle("ls", {"os_name": "Windows"}),
			"CMD",
		)

	def test_script_handle(self):
		interp = MagicMock()
		interp.prompt_builder.get_script_prompt.return_value = "SCRIPT"
		self.assertEqual(
			ScriptModeHandler(interp).handle("write file", {"os_name": "Linux"}),
			"SCRIPT",
		)


if __name__ == "__main__":
	unittest.main()
