"""Unit tests for libs.execution.repairer."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from libs.execution.repairer import RepairCircuitBreaker, Repairer
from libs.execution.safety import ExecutionSafetyManager


class TestRepairCircuitBreaker(unittest.TestCase):
	def test_stops_on_repeated_error(self):
		breaker = RepairCircuitBreaker(max_attempts=3)
		self.assertTrue(breaker.should_continue("ValueError: boom"))
		self.assertFalse(breaker.should_continue("ValueError: boom"))

	def test_stops_after_max_attempts(self):
		breaker = RepairCircuitBreaker(max_attempts=2)
		self.assertTrue(breaker.should_continue("error-a"))
		self.assertTrue(breaker.should_continue("error-b"))
		self.assertFalse(breaker.should_continue("error-c"))

	def test_safety_reexport(self):
		manager = ExecutionSafetyManager(unsafe_mode=False)
		self.assertFalse(manager.unsafe_mode)


class TestRepairer(unittest.TestCase):
	def _interp(self, **kwargs):
		interp = MagicMock()
		interp.COMMAND_MODE = False
		interp.SCRIPT_MODE = False
		interp.CODE_MODE = True
		interp.INTERPRETER_LANGUAGE = "python"
		interp.MAX_REPAIR_ATTEMPTS = 3
		interp.history = []
		interp.config_values = {}
		for k, v in kwargs.items():
			setattr(interp, k, v)
		return interp

	def test_build_repair_prompt_modes(self):
		interp = self._interp()
		prompt = Repairer(interp).build_repair_prompt(
			"print hi", "resolved", "print(x)", "NameError", "Windows", code_output="partial"
		)
		self.assertIn("print hi", prompt)
		self.assertIn("NameError", prompt)
		self.assertIn("Observed stdout", prompt)

		interp.COMMAND_MODE = True
		cmd_prompt = Repairer(interp).build_repair_prompt("t", "p", "cmd", "err", "Linux")
		self.assertIn("terminal command", cmd_prompt)

		interp.COMMAND_MODE = False
		interp.SCRIPT_MODE = True
		script_prompt = Repairer(interp).build_repair_prompt("t", "p", "s", "err", "Linux")
		self.assertIn("script", script_prompt)

	def test_attempt_repair_success(self):
		interp = self._interp()
		interp._build_repair_prompt.side_effect = lambda *a, **k: "repair-prompt"
		interp._generate_content_with_retries.return_value = "```python\nprint(1)\n```"
		interp.code_interpreter.extract_code.return_value = "print(1)"
		interp._maybe_simplify_generated_code.side_effect = lambda task, code: code
		interp._execute_generated_output.return_value = ("1", None, None)
		shown = []
		snippet, output, error = Repairer(interp).attempt_repair_after_failure(
			"print 1",
			"prompt",
			"print(x)",
			"NameError",
			"Windows",
			"```",
			"```",
			None,
			display_code_fn=lambda *a, **k: shown.append(a[0] if a else ""),
			display_markdown_fn=shown.append,
		)
		self.assertEqual(snippet, "print(1)")
		self.assertEqual(output, "1")
		self.assertIsNone(error)

	def test_attempt_repair_extract_failure_then_stop(self):
		interp = self._interp()
		interp.MAX_REPAIR_ATTEMPTS = 1
		interp._build_repair_prompt.return_value = "rp"
		interp._generate_content_with_retries.return_value = "no code"
		interp.code_interpreter.extract_code.return_value = ""
		interp._maybe_simplify_generated_code.side_effect = lambda task, code: code
		snippet, output, error = Repairer(interp).attempt_repair_after_failure(
			"t",
			"p",
			"print(x)",
			"NameError",
			"Windows",
			"```",
			"```",
			None,
			display_code_fn=lambda *a, **k: None,
			display_markdown_fn=lambda *a, **k: None,
		)
		self.assertEqual(snippet, "print(x)")
		self.assertIn("Failed to extract", error)

	def test_attempt_repair_async_success(self):
		interp = self._interp()
		interp._build_repair_prompt.return_value = "rp"
		interp._generate_content_with_retries_async = AsyncMock(
			return_value="```\nprint(9)\n```"
		)
		interp.code_interpreter.extract_code.return_value = "print(9)"
		interp._maybe_simplify_generated_code.side_effect = lambda task, code: code
		interp.executor.execute_async = AsyncMock(return_value=("9", None))
		snippet, output, error = asyncio.run(
			Repairer(interp).attempt_repair_async(
				"t",
				"p",
				"print(x)",
				"NameError",
				"Windows",
				"```",
				"```",
				None,
				display_code_fn=lambda *a, **k: None,
				display_markdown_fn=lambda *a, **k: None,
			)
		)
		self.assertEqual(snippet, "print(9)")
		self.assertEqual(output, "9")


if __name__ == "__main__":
	unittest.main()
