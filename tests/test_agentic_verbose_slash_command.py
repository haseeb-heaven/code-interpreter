# -*- coding: utf-8 -*-
"""Unit tests for the ``--verbose``/``-V`` CLI flag and the in-REPL ``/verbose``
toggle for the ``--agentic`` ReAct loop.

Covers:
  * ``interpreter.py`` argparse accepts ``--verbose``/``-V`` (default ``False``).
  * ``bootstrap_interpreter`` wires ``args.verbose`` into ``interp.VERBOSE_UI``.
  * ``interpreter_agentic_main`` passes ``verbose=`` through to ``ReActController``.
  * The in-REPL ``/verbose`` command toggles ``VERBOSE_UI`` and rebuilds the
    controller (mirroring the existing ``/model``/``/free`` pattern) without
    treating ``/verbose`` itself as a ReAct task.
"""
from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import MagicMock, patch

import interpreter as interpreter_mod

# Pre-import pandas (transitively pulled in by ``libs.data.session_data``,
# which ``bootstrap_interpreter`` lazily imports) so the real ``sys.stdout``
# is used for pandas' module-init console-encoding detection. Otherwise, if
# this happens to be the first import while a test below has ``sys.stdout``
# mocked, pandas' config validator raises unrelated to this feature.
import libs.data.session_data  # noqa: F401


class TestVerboseFlagParsing(unittest.TestCase):
    def test_parser_accepts_verbose_long_flag(self):
        parser = interpreter_mod.build_parser()
        args = parser.parse_args(["--agentic", "--cli", "-m", "gpt-4o", "--verbose"])
        self.assertTrue(args.verbose)

    def test_parser_accepts_verbose_short_flag(self):
        parser = interpreter_mod.build_parser()
        args = parser.parse_args(["--agentic", "--cli", "-m", "gpt-4o", "-V"])
        self.assertTrue(args.verbose)

    def test_verbose_defaults_to_false(self):
        parser = interpreter_mod.build_parser()
        args = parser.parse_args(["--agentic", "--cli", "-m", "gpt-4o"])
        self.assertFalse(args.verbose)

    def test_verbose_does_not_collide_with_version_short_flag(self):
        """``-v``/``--version`` must remain untouched; ``-V`` is the new flag."""
        parser = interpreter_mod.build_parser()
        with self.assertRaises(SystemExit):
            # argparse's `action="version"` exits after printing; this merely
            # confirms `-v` still resolves to `--version`, not `--verbose`.
            parser.parse_args(["-v"])


class TestVerboseBootstrapWiring(unittest.TestCase):
    def _args(self, *, verbose: bool) -> Namespace:
        return Namespace(
            lang="python", save_code=False, exec=False, display_code=False,
            model="gpt-4o", mode="code", file=None, history=False, agent=False,
            yes=True, output_format="plain", no_color=False, search=False,
            stream=False, session=None, list_sessions=False, delete_session=None,
            new_session=False, verbose=verbose,
        )

    def test_bootstrap_interpreter_sets_verbose_ui_from_args(self):
        from libs.core.session import bootstrap_interpreter

        interp = MagicMock()
        interp.args = self._args(verbose=True)
        interp.initialize_client = MagicMock()
        interp.initialize_mode = MagicMock()
        interp.utility_manager = MagicMock()
        interp.logger = MagicMock()
        with patch("libs.core.session.load_system_message", return_value="sys"), \
             patch("libs.output_formatter.sys.stdout") as stdout:
            stdout.isatty.return_value = True
            bootstrap_interpreter(interp)
        self.assertTrue(interp.VERBOSE_UI)

    def test_bootstrap_interpreter_defaults_verbose_ui_false(self):
        from libs.core.session import bootstrap_interpreter

        interp = MagicMock()
        interp.args = self._args(verbose=False)
        interp.initialize_client = MagicMock()
        interp.initialize_mode = MagicMock()
        interp.utility_manager = MagicMock()
        interp.logger = MagicMock()
        with patch("libs.core.session.load_system_message", return_value="sys"), \
             patch("libs.output_formatter.sys.stdout") as stdout:
            stdout.isatty.return_value = True
            bootstrap_interpreter(interp)
        self.assertFalse(interp.VERBOSE_UI)


class TestAgenticReplVerboseToggle(unittest.TestCase):
    """REPL command routing: ``/verbose`` toggles VERBOSE_UI, rebuilds the
    controller, and is never treated as a ReAct task."""

    def _make_interp(self, inputs):
        from libs.interpreter_lib import Interpreter

        args = Namespace(
            lang="python", mode="code", model="local-model", save_code=False, exec=False,
            display_code=False, unsafe=False, sandbox=True, history=False, file=None,
            agent=False, agentic=True, gemini_style=True, cli=True, tui=False, verbose=False,
        )
        printed = []
        with patch.object(Interpreter, "__init__", lambda self, a: None):
            interp = Interpreter(args)
            interp.args = args
            interp.INTERPRETER_MODEL = "local-model"
            interp.INTERPRETER_MODEL_LABEL = "local-model"
            interp.INTERPRETER_PROMPT_FILE = False
            interp.UNSAFE_EXECUTION = False
            interp.MAX_REPAIR_ATTEMPTS = 3
            interp.VERBOSE_UI = False
            interp.terminal_ui = None
            interp.logger = type("L", (), {"error": lambda *a, **k: None})()
            interp.console = type(
                "C",
                (),
                {"print": lambda self, *a, **k: printed.append(" ".join(str(x) for x in a))},
            )()
            it = iter(inputs)
            interp._safe_input = lambda prompt, default="": next(it)
            return interp, printed

    def test_verbose_toggle_flips_flag_and_rebuilds_controller(self):
        interp, printed = self._make_interp(["/verbose", "/exit"])
        with patch("libs.agent.react_controller.ReActController") as mock_ctrl:
            from libs.interpreter_lib import Interpreter

            Interpreter.interpreter_agentic_main(interp)

        self.assertTrue(interp.VERBOSE_UI)
        self.assertTrue(interp.args.verbose)
        # Controller constructed twice: once at REPL start, once after /verbose.
        self.assertGreaterEqual(mock_ctrl.call_count, 2)
        _, last_kwargs = mock_ctrl.call_args
        self.assertTrue(last_kwargs.get("verbose"))
        mock_ctrl.return_value.run.assert_not_called()
        joined = "\n".join(printed).lower()
        self.assertIn("verbose", joined)
        self.assertIn("on", joined)

    def test_verbose_toggle_twice_returns_to_off(self):
        interp, printed = self._make_interp(["/verbose", "/verbose", "/exit"])
        with patch("libs.agent.react_controller.ReActController"):
            from libs.interpreter_lib import Interpreter

            Interpreter.interpreter_agentic_main(interp)
        self.assertFalse(interp.VERBOSE_UI)

    def test_help_mentions_verbose_command(self):
        interp, printed = self._make_interp(["/help", "/exit"])
        with patch("libs.agent.react_controller.ReActController"):
            from libs.interpreter_lib import Interpreter

            Interpreter.interpreter_agentic_main(interp)
        joined = "\n".join(printed)
        self.assertIn("/verbose", joined)


if __name__ == "__main__":
    unittest.main()
