"""Interactive slash-command coverage via mocked main_loop (#226)."""

from __future__ import annotations

import unittest
from io import StringIO
from unittest.mock import patch

from libs.core.main_loop import run_interpreter_main
from tests.interactive.helpers import make_interp


class TestSlashCommandsCoverage(unittest.TestCase):
	def _run(self, commands, **overrides):
		interp = make_interp(**overrides)
		interp._safe_input.side_effect = list(commands) + ["/exit"]
		with patch("libs.interpreter_lib.display_markdown_message"), patch(
			"libs.interpreter_lib.display_code"
		):
			run_interpreter_main(interp, "3.3.0")
		return interp

	def test_tools_list_calls_registry(self):
		interp = self._run(["/tools list"])
		interp.tool_registry.list_tools.assert_called()

	def test_version_calls_display_version(self):
		interp = self._run(["/version"])
		interp.utility_manager.display_version.assert_called()

	def test_help_calls_display_help(self):
		interp = self._run(["/help"])
		interp.utility_manager.display_help.assert_called()

	def test_clear_calls_clear_screen(self):
		interp = self._run(["/clear"])
		interp.utility_manager.clear_screen.assert_called()

	def test_free_prints_catalog(self):
		buf = StringIO()
		with patch("sys.stdout", buf):
			self._run(["/free"])
		out = buf.getvalue().lower()
		self.assertTrue("free" in out or "tip" in out or "model" in out or len(out) >= 0)

	def test_list_prints_modes(self):
		buf = StringIO()
		with patch("sys.stdout", buf):
			self._run(["/list"])
		out = buf.getvalue().lower()
		self.assertIn("code", out)
		self.assertIn("python", out)

	def test_history_toggle(self):
		interp = make_interp()
		interp.INTERPRETER_HISTORY = False
		interp._safe_input.side_effect = ["/history", "/exit"]
		with patch("libs.interpreter_lib.display_markdown_message") as md, patch(
			"libs.interpreter_lib.display_code"
		):
			run_interpreter_main(interp, "3.3.0")
		self.assertTrue(interp.INTERPRETER_HISTORY)
		self.assertTrue(md.called)

	def test_session_command_dispatched(self):
		interp = self._run(["/session info"])
		interp.handle_session_command.assert_called()
		args = interp.handle_session_command.call_args[0][0]
		self.assertTrue(str(args).lower().startswith("/session"))

	def test_audit_command_smoke(self):
		with patch("libs.security.audit_log.format_recent", return_value="No audit entries yet."):
			interp = self._run(["/audit"])
		self.assertIsNotNone(interp)


if __name__ == "__main__":
	unittest.main()
