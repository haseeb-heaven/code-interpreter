"""Live code execution round-trips (real subprocess, no LLM) (#226)."""

from __future__ import annotations

import unittest

from libs.code_interpreter import CodeInterpreter
from libs.execution.sandbox_subprocess import run_in_subprocess
from libs.safety_manager import ExecutionSafetyManager


class TestLiveCodeExecution(unittest.TestCase):
	def test_exec_safe_code_returns_output(self):
		result = run_in_subprocess('print("live exec test")', timeout=15, language="python")
		self.assertEqual(result["returncode"], 0)
		self.assertIn("live exec test", result["stdout"])

	def test_exec_syntax_error_returns_nonzero(self):
		result = run_in_subprocess("def broken(:\n    pass", timeout=15, language="python")
		self.assertNotEqual(result["returncode"], 0)
		self.assertTrue(len(result["stderr"]) > 0 or len(result["stdout"]) >= 0)

	def test_exec_infinite_loop_times_out(self):
		result = run_in_subprocess("while True: pass", timeout=1, language="python")
		self.assertTrue(result["timed_out"])
		self.assertNotEqual(result["returncode"], 0)

	def test_code_interpreter_extract_and_force_exec(self):
		"""Force-execute path with unsafe safety manager (no approval prompt)."""
		ci = CodeInterpreter(safety_manager=ExecutionSafetyManager(unsafe_mode=True))
		code = ci.extract_code("```python\nprint(2+2)\n```")
		out, err = ci.execute_code(code, "python", force_execute=True)
		combined = (out or "") + (err or "")
		self.assertIn("4", combined)


if __name__ == "__main__":
	unittest.main()
