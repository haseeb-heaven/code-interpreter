"""Unit tests for ReAct Debugger action."""
import unittest
from unittest.mock import patch

from libs.agent.actions.debugger import DebuggerAction


class TestDebuggerAction(unittest.TestCase):
    @patch("libs.agent.actions.debugger.call_llm")
    def test_returns_diagnosis(self, mock_llm):
        mock_llm.return_value = (
            "Root cause: NameError. Fix: define x before use.",
            {"cost": 0.02, "tokens": 30},
        )
        debugger = DebuggerAction(model_name="gpt-4o", api_key="test")
        result = debugger.run(
            task="print x",
            code="print(x)",
            error="NameError: x",
            last_observation="ERROR: NameError",
        )
        self.assertIn("NameError", result.observation)
        self.assertIn("Fix", result.observation)
        self.assertEqual(result.metrics["tokens"], 30)


if __name__ == "__main__":
    unittest.main()
