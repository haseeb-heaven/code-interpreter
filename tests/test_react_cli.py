"""CLI wiring tests for --agentic flag."""
import unittest
from unittest.mock import MagicMock, patch

import interpreter as interpreter_mod


class TestAgenticCLI(unittest.TestCase):
    def test_parser_accepts_agentic_flag(self):
        parser = interpreter_mod.build_parser()
        args = parser.parse_args(["--agentic", "--cli", "--mode", "code", "--model", "gpt-4o"])
        self.assertTrue(args.agentic)

    @patch("interpreter.Interpreter")
    def test_main_routes_to_agentic(self, mock_interpreter_cls):
        instance = MagicMock()
        mock_interpreter_cls.return_value = instance
        interpreter_mod.main(["interpreter.py", "--agentic", "--cli", "--mode", "code", "--model", "gpt-4o"])
        instance.interpreter_agentic_main.assert_called_once()
        instance.interpreter_main.assert_not_called()


if __name__ == "__main__":
    unittest.main()
