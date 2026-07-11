"""Unit tests for libs.execution.repairer."""

from __future__ import annotations

import unittest

from libs.execution.repairer import RepairCircuitBreaker
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


if __name__ == "__main__":
	unittest.main()
