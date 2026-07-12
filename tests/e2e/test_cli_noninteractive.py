"""Non-interactive CLI end-to-end tests (no human input required)."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable


class TestCliHelpAndFlags(unittest.TestCase):
    def test_help_lists_agent_flags(self):
        proc = subprocess.run(
            [PYTHON, str(ROOT / "interpreter.py"), "--help"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout + proc.stderr
        self.assertIn("--agent", out)
        self.assertIn("--agentic", out)
        self.assertIn("--yes", out)

    def test_version_exits_zero(self):
        proc = subprocess.run(
            [PYTHON, str(ROOT / "interpreter.py"), "--version"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertRegex(proc.stdout + proc.stderr, r"3\.\d+")

    def test_parser_yes_flag(self):
        import interpreter as interpreter_mod

        args = interpreter_mod.build_parser().parse_args(
            ["--agent", "--yes", "--cli", "--mode", "code", "-m", "gpt-4o", "-f", "task.txt"]
        )
        self.assertTrue(args.agent)
        self.assertTrue(args.yes)
        self.assertEqual(args.file, "task.txt")


class TestAutoYesSafeInput(unittest.TestCase):
    def test_safe_input_auto_confirms_execute_prompt(self):
        from libs.interpreter_lib import Interpreter

        interp = MagicMock()
        interp.AUTO_YES = True
        interp.logger = MagicMock()
        result = Interpreter._safe_input(interp, "Execute the prompt (Y/N/P/C)?: ", default="n")
        self.assertEqual(result, "y")

    def test_safe_input_auto_yes_still_reads_generic_prompt(self):
        """AUTO_YES must not short-circuit task/REPL prompts to the default."""
        from libs.interpreter_lib import Interpreter

        interp = MagicMock()
        interp.AUTO_YES = True
        interp.logger = MagicMock()
        with patch("builtins.input", return_value="do something"):
            result = Interpreter._safe_input(interp, "> ", default="/exit")
        self.assertEqual(result, "do something")

    def test_safe_input_eof_returns_default_under_auto_yes(self):
        from libs.interpreter_lib import Interpreter

        interp = MagicMock()
        interp.AUTO_YES = True
        interp.logger = MagicMock()
        with patch("builtins.input", side_effect=EOFError):
            result = Interpreter._safe_input(interp, "> ", default="/exit")
        self.assertEqual(result, "/exit")


class TestNonInteractiveAgentMainLoop(unittest.TestCase):
    def test_agent_mode_file_yes_one_shot(self):
        """File + AUTO_YES + AGENT_MODE runs pipeline once and exits (no input())."""
        from libs.agents.base_agent import AgentContext
        from libs.core.main_loop import run_interpreter_main

        with tempfile.TemporaryDirectory() as tmp:
            task_path = Path(tmp) / "task.txt"
            task_path.write_text("print hello and sum 1 to 10", encoding="utf-8")

            ctx = AgentContext(
                task="print hello and sum 1 to 10",
                os_name="Windows",
                language="python",
                intent="code",
                plan=["print"],
                code="print(55)",
                output="Hello\nSum of 1..10 = 55\n",
                error="",
                safe=True,
                verified=True,
                approved=True,
                metadata={"review_reason": "ok", "mode": "code"},
            )

            interp = MagicMock()
            interp.args = MagicMock(file=str(task_path))
            interp.INTERPRETER_PROMPT_FILE = True
            interp.INTERPRETER_PROMPT_INPUT = False
            interp.AUTO_YES = True
            interp.AGENT_MODE = True
            interp.SCRIPT_MODE = False
            interp.COMMAND_MODE = False
            interp.VISION_MODE = False
            interp.CHAT_MODE = False
            interp.INTERPRETER_MODE = "code"
            interp.INTERPRETER_LANGUAGE = "python"
            interp.INTERPRETER_MODEL = "gpt-4o"
            interp.INTERPRETER_MODEL_LABEL = "gpt-4o"
            interp.UNSAFE_EXECUTION = False
            interp.DISPLAY_CODE = False
            interp.SAVE_CODE = False
            interp.EXECUTE_CODE = False
            interp.config_values = {"start_sep": "```", "end_sep": "```"}
            interp.logger = MagicMock()
            interp.console = MagicMock()
            interp.utility_manager = MagicMock()
            interp.utility_manager.get_os_platform.return_value = ("Windows",)
            interp.utility_manager.read_file.return_value = "print hello and sum 1 to 10"
            interp.history_manager = MagicMock()
            interp.package_manager = MagicMock()
            interp.run_agent_pipeline.return_value = ctx
            interp._safe_input.side_effect = AssertionError("input() must not be called in --yes mode")
            interp._display_session_banner = MagicMock()
            interp._is_recoverable_runtime_error.return_value = False

            run_interpreter_main(interp, "3.4.0")

            interp.run_agent_pipeline.assert_called_once()
            interp.utility_manager.read_file.assert_called()
            # Must not fall through to interactive input
            interp._safe_input.assert_not_called()


class TestNonInteractiveAgenticEntry(unittest.TestCase):
    def test_agentic_main_uses_file_and_react_controller(self):
        from libs.interpreter_lib import Interpreter

        with tempfile.TemporaryDirectory() as tmp:
            task_path = Path(tmp) / "react_task.txt"
            task_path.write_text("Print hello", encoding="utf-8")

            interp = MagicMock(spec=Interpreter)
            interp.args = MagicMock(file=str(task_path))
            interp.INTERPRETER_PROMPT_FILE = True
            interp.INTERPRETER_MODEL = "gpt-4o"
            interp.UNSAFE_EXECUTION = False
            interp.MAX_REPAIR_ATTEMPTS = 3
            interp.console = MagicMock()
            interp.logger = MagicMock()
            interp._safe_input.side_effect = AssertionError("no interactive task prompt")

            with patch("libs.agent.react_controller.ReActController") as mock_cls:
                mock_cls.return_value.run.return_value = {"status": "COMPLETED"}
                Interpreter.interpreter_agentic_main(interp)

            mock_cls.assert_called_once()
            mock_cls.return_value.run.assert_called_once_with("Print hello")
            interp._safe_input.assert_not_called()


class TestPrepareArgsAutoYesFromCI(unittest.TestCase):
    def test_ci_env_enables_yes(self):
        import interpreter as interpreter_mod

        with patch.dict(os.environ, {"CI": "true", "INTERPRETER_YES": ""}, clear=False):
            parser = interpreter_mod.build_parser()
            args = parser.parse_args(["--cli", "--mode", "code", "-m", "gpt-4o"])
            args = interpreter_mod.prepare_args(args, ["interpreter.py", "--cli"])
            self.assertTrue(args.yes)


if __name__ == "__main__":
    unittest.main()
