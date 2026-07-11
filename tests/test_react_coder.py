"""Unit tests for ReAct Coder action."""
import unittest
from unittest.mock import MagicMock, patch

from libs.agent.actions.coder import CoderAction


class TestCoderAction(unittest.TestCase):
    @patch("libs.agent.actions.coder.call_llm")
    def test_returns_extracted_python_code(self, mock_llm):
        mock_llm.return_value = (
            "```python\nprint('hello')\n```",
            {"cost": 0.01, "tokens": 20},
        )
        coder = CoderAction(model_name="gpt-4o", api_key="test")
        result = coder.run(
            instruction="print hello",
            task="Say hello",
            current_code="",
            history="",
        )
        self.assertEqual(result.observation, "print('hello')")
        self.assertEqual(result.code, "print('hello')")
        self.assertEqual(result.metrics["tokens"], 20)

    @patch("libs.agent.actions.coder.call_llm")
    def test_raises_when_llm_fails(self, mock_llm):
        mock_llm.side_effect = RuntimeError("LLM down")
        coder = CoderAction(model_name="gpt-4o", api_key="test")
        with self.assertRaises(RuntimeError):
            coder.run(instruction="x", task="t", current_code="", history="")


if __name__ == "__main__":
    unittest.main()
