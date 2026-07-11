"""Unit tests for ReAct Reviewer action."""
import unittest
from unittest.mock import patch

from libs.agent.actions.reviewer import ReviewerAction


class TestReviewerAction(unittest.TestCase):
    @patch("libs.agent.actions.reviewer.call_llm")
    def test_passed_true(self, mock_llm):
        mock_llm.return_value = (
            '{"passed": true, "reason": "Output matches task"}',
            {"cost": 0.0, "tokens": 5},
        )
        reviewer = ReviewerAction(model_name="gpt-4o", api_key="test")
        result = reviewer.run(
            task="print 1",
            code="print(1)",
            execution_result="SUCCESS OUTPUT: 1",
        )
        self.assertTrue(result.passed)
        self.assertIn("matches", result.reason.lower())

    @patch("libs.agent.actions.reviewer.call_llm")
    def test_passed_false(self, mock_llm):
        mock_llm.return_value = (
            '{"passed": false, "reason": "Wrong output"}',
            {"cost": 0.0, "tokens": 5},
        )
        reviewer = ReviewerAction(model_name="gpt-4o", api_key="test")
        result = reviewer.run(task="t", code="c", execution_result="err")
        self.assertFalse(result.passed)

    @patch("libs.agent.actions.reviewer.call_llm")
    def test_yes_no_fallback(self, mock_llm):
        mock_llm.return_value = ("YES - looks good", {"cost": 0.0, "tokens": 3})
        reviewer = ReviewerAction(model_name="gpt-4o", api_key="test")
        result = reviewer.run(task="t", code="c", execution_result="ok")
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
