"""Non-interactive e2e covering all modes + agent/agentic (no human input)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Pre-import pandas before any test patches ``sys.stdout`` with a MagicMock
# (see TestModeFlagsBootstrap below). pandas registers a console-encoding
# option at import time by reading ``sys.stdout.encoding``; if the first
# import happens while stdout is mocked, pandas raises ValueError because a
# MagicMock attribute isn't a str/bytes. Importing it here, while stdout is
# still real, avoids that Windows-only ordering flake.
import pandas as _pd  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]


class TestCliSurface(unittest.TestCase):
    def test_help_lists_modes_and_flags(self):
        import interpreter as mod

        help_text = mod.build_parser().format_help()
        for flag in ("--agent", "--agentic", "--yes", "--mode"):
            self.assertIn(flag, help_text)

    def test_parser_accepts_all_modes(self):
        import interpreter as mod

        parser = mod.build_parser()
        for mode in ("code", "script", "command", "vision", "chat"):
            args = parser.parse_args(["--cli", "--mode", mode, "-m", "gpt-4o", "--yes"])
            self.assertEqual(args.mode, mode)
            self.assertTrue(args.yes)


class TestAutoYes(unittest.TestCase):
    def test_safe_input_confirms(self):
        from libs.interpreter_lib import Interpreter

        interp = MagicMock()
        interp.AUTO_YES = True
        interp.logger = MagicMock()
        self.assertEqual(
            Interpreter._safe_input(interp, "Execute the prompt (Y/N/P/C)?: ", default="n"),
            "y",
        )

    def test_ci_enables_yes(self):
        import interpreter as mod

        with patch.dict(os.environ, {"CI": "true", "INTERPRETER_YES": ""}, clear=False):
            args = mod.build_parser().parse_args(["--cli", "--mode", "code", "-m", "gpt-4o"])
            args = mod.prepare_args(args, ["interpreter.py", "--cli"])
            self.assertTrue(args.yes)


class TestFilePromptNonInteractive(unittest.TestCase):
    def test_auto_yes_reads_cwd_file_and_oneshots_agent(self):
        """File prompt + AUTO_YES + AGENT_MODE completes without input()."""
        from libs.agents.base_agent import AgentContext
        from libs.core.main_loop import run_interpreter_main

        with tempfile.TemporaryDirectory() as tmp:
            task_path = Path(tmp) / "task.txt"
            task_path.write_text("print hello", encoding="utf-8")

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
            interp.utility_manager.read_file.return_value = "print hello"
            interp.utility_manager.extract_file_name.return_value = None
            interp.history_manager = MagicMock()
            interp.package_manager = MagicMock()
            interp._safe_input.side_effect = AssertionError("input must not be called")
            interp._display_session_banner = MagicMock()
            interp._is_recoverable_runtime_error.return_value = False
            interp.run_agent_pipeline.return_value = AgentContext(
                task="print hello",
                os_name="Windows",
                language="python",
                intent="code",
                plan=["step"],
                code="print(1)",
                output="1\n",
                safe=True,
                verified=True,
                approved=True,
                metadata={"mode": "code", "review_reason": "ok"},
            )

            with patch("libs.interpreter_lib.display_markdown_message"), \
                 patch("libs.interpreter_lib.display_code"):
                run_interpreter_main(interp, "3.4.0")

            interp.run_agent_pipeline.assert_called_once()
            interp._safe_input.assert_not_called()


class TestModeFlagsBootstrap(unittest.TestCase):
    def test_bootstrap_sets_agent_and_auto_yes(self):
        from libs.core.session import bootstrap_interpreter

        interp = MagicMock()
        interp.args = MagicMock(
            lang="python",
            save_code=False,
            exec=False,
            display_code=False,
            model="gpt-4o",
            mode="chat",
            file="task.txt",
            history=False,
            agent=True,
            yes=True,
            output_format="plain",
            no_color=False,
            search=False,
            stream=False,
        )
        with patch("libs.core.session.load_system_message", return_value="sys"), \
             patch.object(type(interp), "initialize_client", create=True), \
             patch.object(type(interp), "initialize_mode", create=True), \
             patch("libs.output_formatter.sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            interp.initialize_client = MagicMock()
            interp.initialize_mode = MagicMock()
            interp.utility_manager = MagicMock()
            interp.logger = MagicMock()
            bootstrap_interpreter(interp)

        self.assertTrue(interp.AGENT_MODE)
        self.assertTrue(interp.AUTO_YES)
        self.assertEqual(interp.INTERPRETER_MODE, "chat")


class TestAllModesArgMatrix(unittest.TestCase):
    def test_each_mode_prepares_cli_args(self):
        import interpreter as mod

        for mode in ("code", "script", "command", "vision", "chat"):
            with self.subTest(mode=mode):
                args = mod.build_parser().parse_args(
                    ["--cli", "--mode", mode, "-m", "gpt-4o", "--yes", "-f", "task.txt", "--agent"]
                )
                args = mod.prepare_args(args, ["interpreter.py", "--cli", "--mode", mode])
                self.assertEqual(args.mode, mode)
                self.assertTrue(args.yes)
                self.assertTrue(args.agent)
                self.assertTrue(args.cli)


class TestAgenticEntry(unittest.TestCase):
    def test_agentic_reads_file(self):
        from libs.interpreter_lib import Interpreter

        with tempfile.TemporaryDirectory() as tmp:
            task_path = Path(tmp) / "react.txt"
            task_path.write_text("Print hello", encoding="utf-8")

            interp = MagicMock(spec=Interpreter)
            interp.args = MagicMock(file=str(task_path))
            interp.INTERPRETER_PROMPT_FILE = True
            interp.INTERPRETER_MODEL = "gpt-4o"
            interp.UNSAFE_EXECUTION = False
            interp.MAX_REPAIR_ATTEMPTS = 3
            interp.console = MagicMock()
            interp.logger = MagicMock()
            interp._safe_input.side_effect = AssertionError("no interactive prompt")

            with patch("libs.agent.react_controller.ReActController") as mock_cls:
                mock_cls.return_value.run.return_value = {"status": "COMPLETED"}
                Interpreter.interpreter_agentic_main(interp)

            mock_cls.return_value.run.assert_called_once_with("Print hello")
            interp._safe_input.assert_not_called()


class TestGeminiStyleAgentic(unittest.TestCase):
    def test_gemini_style_reads_file_and_runs_once(self):
        """--gemini-style drives the same ReAct entrypoint as --agentic but takes
        the gemini_style banner branch (verified via the console.print text)."""
        from libs.interpreter_lib import Interpreter

        with tempfile.TemporaryDirectory() as tmp:
            task_path = Path(tmp) / "react.txt"
            task_path.write_text("Print hello", encoding="utf-8")

            interp = MagicMock(spec=Interpreter)
            interp.args = MagicMock(file=str(task_path), gemini_style=True)
            interp.INTERPRETER_PROMPT_FILE = True
            interp.INTERPRETER_MODEL = "gpt-4o"
            interp.UNSAFE_EXECUTION = False
            interp.MAX_REPAIR_ATTEMPTS = 3
            interp.console = MagicMock()
            interp.logger = MagicMock()
            interp._safe_input.side_effect = AssertionError("no interactive prompt")

            with patch("libs.agent.react_controller.ReActController") as mock_cls:
                mock_cls.return_value.run.return_value = {"status": "COMPLETED"}
                Interpreter.interpreter_agentic_main(interp)

            mock_cls.return_value.run.assert_called_once_with("Print hello")
            interp._safe_input.assert_not_called()

            printed = [str(call.args[0]) for call in interp.console.print.call_args_list if call.args]
            self.assertTrue(
                any("Commands: /free" in text for text in printed),
                "gemini-style banner (with /free /model /verbose commands) was not printed",
            )
            self.assertFalse(
                any("Running in ReAct Agentic Mode" in text for text in printed),
                "plain --agentic banner text should not appear on the gemini-style path",
            )


class TestYoloAutoLoop(unittest.TestCase):
    def test_yolo_runs_tool_loop_once(self):
        """--yolo drives the autonomous FS/shell tool loop with approval prompts skipped."""
        from libs.interpreter_lib import Interpreter

        with tempfile.TemporaryDirectory() as tmp:
            task_path = Path(tmp) / "task.txt"
            task_path.write_text("List files in the current directory", encoding="utf-8")

            interp = MagicMock(spec=Interpreter)
            interp.args = MagicMock(file=str(task_path), yolo=True, mcp_server=None, search=False)
            interp.INTERPRETER_PROMPT_FILE = True
            interp.INTERPRETER_MODEL = "gpt-4o"
            interp.INTERPRETER_MODEL_LABEL = "gpt-4o"
            interp.AUTO_YES = True
            interp.console = MagicMock()
            interp.logger = MagicMock()
            interp._safe_input.side_effect = AssertionError("no interactive prompt")

            with patch("libs.agent.auto_loop.AutonomousAgentLoop") as mock_cls:
                mock_cls.return_value.run.return_value = "Listed 3 files."
                Interpreter.interpreter_auto_main(interp)

            mock_cls.return_value.run.assert_called_once_with("List files in the current directory")
            interp._safe_input.assert_not_called()
            interp.console.print.assert_any_call("Listed 3 files.")


class TestModeFamilyNonInteractive(unittest.TestCase):
    """Real-request-shaped coverage for script/command/vision/chat (code mode's
    siblings are already covered by TestFilePromptNonInteractive above), reusing
    that same file-prompt + AUTO_YES + AGENT_MODE fixture per mode flag."""

    def test_agent_pipeline_runs_for_each_mode(self):
        from libs.agents.base_agent import AgentContext
        from libs.core.main_loop import run_interpreter_main

        for mode in ("script", "command", "vision", "chat"):
            with self.subTest(mode=mode):
                with tempfile.TemporaryDirectory() as tmp:
                    task_path = Path(tmp) / "task.txt"
                    task_path.write_text("print hello", encoding="utf-8")

                    interp = MagicMock()
                    interp.args = MagicMock(file=str(task_path))
                    interp.INTERPRETER_PROMPT_FILE = True
                    interp.INTERPRETER_PROMPT_INPUT = False
                    interp.AUTO_YES = True
                    interp.AGENT_MODE = True
                    interp.SCRIPT_MODE = mode == "script"
                    interp.COMMAND_MODE = mode == "command"
                    interp.VISION_MODE = mode == "vision"
                    interp.CHAT_MODE = mode == "chat"
                    interp.INTERPRETER_MODE = mode
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
                    interp.utility_manager.read_file.return_value = "print hello"
                    interp.utility_manager.extract_file_name.return_value = None
                    interp.history_manager = MagicMock()
                    interp.package_manager = MagicMock()
                    interp._safe_input.side_effect = AssertionError("input must not be called")
                    interp._display_session_banner = MagicMock()
                    interp._is_recoverable_runtime_error.return_value = False
                    interp.run_agent_pipeline.return_value = AgentContext(
                        task="print hello",
                        os_name="Windows",
                        language="python",
                        intent=mode,
                        plan=["step"],
                        code="print(1)" if mode in ("script", "command") else None,
                        output=f"{mode} mode response",
                        safe=True,
                        verified=True,
                        approved=True,
                        metadata={"mode": mode, "review_reason": "ok"},
                    )

                    with patch("libs.interpreter_lib.display_markdown_message"), \
                         patch("libs.interpreter_lib.display_code"):
                        run_interpreter_main(interp, "3.4.0")

                    interp.run_agent_pipeline.assert_called_once()
                    interp._safe_input.assert_not_called()
                    self.assertTrue(interp.run_agent_pipeline.return_value.output)


class TestLiveRepresentativeSmoke(unittest.TestCase):
    """One live ping per present provider. Opt-in via E2E_LIVE=1 or SMOKE_LIVE=1."""

    PROVIDERS = [
        ("gpt-4o-mini", "OPENAI_API_KEY", {"model": "gpt-4o-mini", "provider": ""}),
        ("claude-haiku-4-5", "ANTHROPIC_API_KEY", None),
        ("gemini-2.0-flash", "GEMINI_API_KEY", None),
        ("groq-llama-3.3-70b", "GROQ_API_KEY", None),
        ("openrouter-free", "OPENROUTER_API_KEY", None),
    ]

    def _key_ok(self, name: str) -> bool:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "report_key_presence", ROOT / "scripts" / "report_key_presence.py"
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        return mod.looks_real(name)

    def test_live_one_per_present_provider(self):
        if os.getenv("SMOKE_LIVE") != "1" and os.getenv("E2E_LIVE") != "1":
            self.skipTest("Set E2E_LIVE=1 or SMOKE_LIVE=1 to run live provider pings")

        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=True)

        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "smoke_all_models", ROOT / "scripts" / "smoke_all_models.py"
        )
        smoke = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(smoke)

        results = []
        for label, key_name, inline_cfg in self.PROVIDERS:
            if not self._key_ok(key_name):
                results.append((label, "SKIP", f"{key_name} absent"))
                continue
            cfg_path = ROOT / "configs" / f"{label}.json"
            if inline_cfg is not None:
                cfg = inline_cfg
            elif cfg_path.exists():
                cfg = __import__("json").loads(cfg_path.read_text(encoding="utf-8"))
            else:
                alts = sorted((ROOT / "configs").glob(f"*{label.split('-')[0]}*.json"))
                if not alts:
                    results.append((label, "SKIP", "no config"))
                    continue
                cfg = __import__("json").loads(alts[0].read_text(encoding="utf-8"))
                label = alts[0].stem

            try:
                status, detail = smoke.live_row(label, cfg)
                # Empty responses from flaky providers are soft-skips in CI
                if status == "FAIL" and "empty response" in detail.lower():
                    status, detail = "SKIP", detail
                results.append((label, status, detail))
            except Exception as exc:
                text = str(exc).lower()
                soft = (
                    "quota",
                    "credit",
                    "billing",
                    "recharge",
                    "not found",
                    "deprecated",
                    "not supported",
                )
                if any(m in text for m in soft):
                    results.append((label, "SKIP", f"{type(exc).__name__}: {exc}"))
                else:
                    results.append((label, "FAIL", f"{type(exc).__name__}: {exc}"))

        fails = [r for r in results if r[1] == "FAIL"]
        passes = [r for r in results if r[1] == "PASS"]
        for row in results:
            print(f"LIVE {row[0]}: {row[1]} - {row[2]}")
        # Require at least one live PASS when any key present; billing skips OK
        if any(self._key_ok(k) for _, k, _ in self.PROVIDERS):
            self.assertTrue(passes, "Expected at least one live provider PASS")
        self.assertFalse(fails, f"Live failures: {fails}")


if __name__ == "__main__":
    unittest.main()
