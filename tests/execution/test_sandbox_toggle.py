"""Unit tests for SAFE/UNSAFE sandbox toggle helper."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from libs.execution.sandbox_toggle import toggle_sandbox_mode


class TestSandboxToggle(unittest.TestCase):
	def _interp(self, unsafe=False):
		interp = MagicMock()
		interp.UNSAFE_EXECUTION = unsafe
		interp.safety_manager = MagicMock()
		interp.safety_manager.unsafe_mode = unsafe
		interp.code_interpreter = MagicMock()
		interp.code_interpreter.UNSAFE_EXECUTION = unsafe
		interp.logger = MagicMock()
		return interp

	def test_disable_cancelled_keeps_sandbox(self):
		interp = self._interp(unsafe=False)
		displayed = []
		result = toggle_sandbox_mode(
			interp,
			display_fn=displayed.append,
			input_fn=lambda *_a, **_k: "no",
		)
		self.assertTrue(result)
		self.assertFalse(interp.UNSAFE_EXECUTION)
		self.assertTrue(any("ENABLED" in msg for msg in displayed))

	def test_disable_confirmed_enables_unsafe(self):
		interp = self._interp(unsafe=False)
		displayed = []
		result = toggle_sandbox_mode(
			interp,
			display_fn=displayed.append,
			input_fn=lambda *_a, **_k: "yes",
		)
		self.assertFalse(result)
		self.assertTrue(interp.UNSAFE_EXECUTION)
		self.assertTrue(interp.safety_manager.unsafe_mode)
		self.assertTrue(interp.code_interpreter.UNSAFE_EXECUTION)
		interp.logger.warning.assert_called()

	def test_enable_from_unsafe(self):
		interp = self._interp(unsafe=True)
		displayed = []
		result = toggle_sandbox_mode(
			interp,
			display_fn=displayed.append,
			input_fn=lambda *_a, **_k: "no",
		)
		self.assertTrue(result)
		self.assertFalse(interp.UNSAFE_EXECUTION)
		self.assertFalse(interp.safety_manager.unsafe_mode)
		self.assertTrue(any("SANDBOX ENABLED" in msg for msg in displayed))


if __name__ == "__main__":
	unittest.main()
