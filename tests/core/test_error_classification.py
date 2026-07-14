# -*- coding: utf-8 -*-
"""Tests for the shared billing/auth/dependency error classification constants."""

from __future__ import annotations

import unittest

from libs.core.error_classification import (
	BILLING_AUTH_MARKERS,
	DEPENDENCY_ENV_MARKERS,
	is_billing_or_auth_condition,
)


class TestErrorClassification(unittest.TestCase):
	def test_billing_auth_markers_cover_common_quota_errors(self):
		for marker in ("429", "rate limit", "quota", "insufficient balance", "unauthorized"):
			self.assertIn(marker, BILLING_AUTH_MARKERS)

	def test_dependency_env_markers_cover_common_local_errors(self):
		for marker in ("modulenotfounderror", "connection refused", "timeout"):
			self.assertIn(marker, DEPENDENCY_ENV_MARKERS)

	def test_is_billing_or_auth_condition_true_for_quota_text(self):
		self.assertTrue(is_billing_or_auth_condition("Error: 429 rate limit exceeded"))
		self.assertTrue(is_billing_or_auth_condition("insufficient balance on account"))

	def test_is_billing_or_auth_condition_false_for_unrelated_text(self):
		self.assertFalse(is_billing_or_auth_condition("division by zero"))


if __name__ == "__main__":
	unittest.main()
