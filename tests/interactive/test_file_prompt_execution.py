"""-f / --file prompt file execution through main_loop (#226)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from libs.core.main_loop import run_interpreter_main
from tests.interactive.helpers import make_interp


class TestFilePromptExecution(unittest.TestCase):
	def test_file_content_used_as_first_prompt(self):
		"""When -f is passed with AUTO_YES, file text becomes the task."""
		with tempfile.TemporaryDirectory() as tmp:
			fpath = Path(tmp) / "task.txt"
			fpath.write_text("what is 2 + 2?", encoding="utf-8")

			interp = make_interp()
			interp.INTERPRETER_PROMPT_FILE = True
			interp.INTERPRETER_PROMPT_INPUT = False
			interp.AUTO_YES = True
			interp.args.file = str(fpath)
			interp.CHAT_MODE = True
			interp.CODE_MODE = False
			interp.INTERPRETER_MODE = "chat"
			interp._generate_content_with_retries = MagicMock(return_value="4")
			interp._safe_input.side_effect = ["/exit"]

			with patch("libs.interpreter_lib.display_markdown_message"), patch(
				"libs.interpreter_lib.display_code"
			):
				run_interpreter_main(interp, "3.3.0")

			interp._generate_content_with_retries.assert_called()
			# First positional prompt should include file contents
			call_args = interp._generate_content_with_retries.call_args
			prompt_arg = call_args[0][0] if call_args[0] else ""
			self.assertIn("2 + 2", str(prompt_arg))

	def test_missing_file_auto_yes_exits_cleanly(self):
		interp = make_interp()
		interp.INTERPRETER_PROMPT_FILE = True
		interp.INTERPRETER_PROMPT_INPUT = False
		interp.AUTO_YES = True
		interp.args.file = "definitely_missing_prompt_226.txt"

		with patch("libs.interpreter_lib.display_markdown_message") as md, patch(
			"libs.interpreter_lib.display_code"
		):
			run_interpreter_main(interp, "3.3.0")
		self.assertTrue(md.called)
		interp._generate_content_with_retries.assert_not_called()


if __name__ == "__main__":
	unittest.main()
