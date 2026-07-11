"""Multi-turn REPL loop coverage with mocked LLM (#226)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from libs.core.main_loop import run_interpreter_main
from tests.interactive.helpers import make_interp

FAKE_LLM_RESPONSE = "```python\nprint('hello from test')\n```"


class TestReplLoop(unittest.TestCase):
	def test_single_turn_code_response(self):
		"""LLM returns a code block → extract → execute → show output."""
		interp = make_interp()
		interp._safe_input.side_effect = ["write hello world script", "/exit"]
		interp._generate_content_with_retries = MagicMock(return_value=FAKE_LLM_RESPONSE)
		interp._execute_generated_output = MagicMock(
			return_value=("hello from test\n", None, None)
		)

		with patch("libs.interpreter_lib.display_markdown_message"), patch(
			"libs.interpreter_lib.display_code"
		):
			run_interpreter_main(interp, "3.3.0")

		interp._generate_content_with_retries.assert_called()
		interp._execute_generated_output.assert_called()
		interp.code_interpreter.extract_code.assert_called()
		interp.history_manager.save_history_json.assert_called()

	def test_multi_turn_history_persisted(self):
		"""Each turn records history via history_manager."""
		interp = make_interp()
		interp._safe_input.side_effect = ["turn 1", "turn 2", "/exit"]
		interp._generate_content_with_retries = MagicMock(return_value="No code needed.")
		interp.code_interpreter.extract_code.side_effect = lambda text, *a, **k: None

		with patch("libs.interpreter_lib.display_markdown_message"), patch(
			"libs.interpreter_lib.display_code"
		):
			run_interpreter_main(interp, "3.3.0")

		self.assertGreaterEqual(interp.history_manager.save_history_json.call_count, 2)

	def test_execution_error_triggers_package_retry_path(self):
		"""ModuleNotFound error attempts install + re-execute."""
		interp = make_interp()
		interp._safe_input.side_effect = ["import missinglib", "/exit"]
		interp._generate_content_with_retries = MagicMock(return_value=FAKE_LLM_RESPONSE)
		interp._execute_generated_output = MagicMock(
			side_effect=[
				(None, "ModuleNotFoundError: No module named 'missinglib'", None),
				("fixed\n", None, None),
			]
		)
		interp.package_manager.extract_package_name.return_value = "missinglib"
		interp.package_manager.install_package = MagicMock()

		with patch("libs.interpreter_lib.display_markdown_message"), patch(
			"libs.interpreter_lib.display_code"
		), patch("libs.core.main_loop.time.sleep", return_value=None):
			run_interpreter_main(interp, "3.3.0")

		self.assertGreaterEqual(interp._execute_generated_output.call_count, 2)
		interp.package_manager.install_package.assert_called()


if __name__ == "__main__":
	unittest.main()
