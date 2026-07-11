"""TC003 — Safety manager blocks dangerous code in SAFE mode."""

from __future__ import annotations

import unittest

from libs.safety_manager import ExecutionSafetyManager


class TC003_Safety_Manager_Blocks_Dangerous_Code(unittest.TestCase):
	def test_blocks_rm_rf_in_safe_mode(self):
		manager = ExecutionSafetyManager(unsafe_mode=False)
		decision = manager.assess_execution("import os\nos.system('rm -rf /')", "code")
		self.assertFalse(decision.allowed)
		self.assertTrue(decision.reasons)

	def test_allows_simple_print(self):
		manager = ExecutionSafetyManager(unsafe_mode=False)
		decision = manager.assess_execution("print('hello')", "code")
		self.assertTrue(decision.allowed)


if __name__ == "__main__":
	unittest.main()
