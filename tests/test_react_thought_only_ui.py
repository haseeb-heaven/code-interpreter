# -*- coding: utf-8 -*-
"""Unit tests for the new default Thought-only ``--agentic`` console view.

Covers the ``ReActController``/``GeminiStepPresenter`` wiring for:
  * Default (``verbose=False``): only "Thought" panels render, back-to-back;
    "Action"/"Observation" panels and the ``_on_llm_fallback`` console noise
    are suppressed.
  * ``verbose=True`` (``--verbose``/``-V`` or the in-REPL ``/verbose`` toggle):
    restores the full legacy interleaved Thought -> Action -> Observation view
    plus the "Free model fallback" console line.
  * The final "finish" result always surfaces via ``show_result``, regardless
    of verbosity — it's the task's actual deliverable, not step noise.
  * Trajectory/telemetry JSONL logging is unaffected by verbosity either way.
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from rich.console import Console

from libs.agent.llm import is_verbose_console, set_verbose_console
from libs.agent.react_controller import ReActController
from libs.agent.step_ui import GeminiStepPresenter

_RESPONSES = [
    (
        "Thought: Write code to print hello\nAction: code\nAction Input: {\"instruction\": \"print hello\"}\n",
        {"cost": 0.0, "tokens": 1},
    ),
    (
        "Thought: Execute the script\nAction: execute\nAction Input: {\"language\": \"python\"}\n",
        {"cost": 0.0, "tokens": 1},
    ),
    (
        "Thought: Review the output\nAction: review\nAction Input: {}\n",
        {"cost": 0.0, "tokens": 1},
    ),
    (
        "Thought: Task is done\nAction: finish\nAction Input: {\"summary\": \"printed hello successfully\"}\n",
        {"cost": 0.0, "tokens": 1},
    ),
]


def _make_gemini_controller(*, verbose, tmp_dir, code_interpreter, safety):
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=120, color_system=None)
    presenter = GeminiStepPresenter(console=console, verbose=verbose)
    controller = ReActController(
        model_name="gpt-4o",
        api_key="test",
        code_interpreter=code_interpreter,
        safety_manager=safety,
        log_path=os.path.join(tmp_dir, "agent_react.jsonl"),
        max_steps=10,
        gemini_style=True,
        verbose=verbose,
        step_presenter=presenter,
        auto_yes=True,
    )
    return controller, buf


class ReActControllerThoughtOnlyDefaultTests(unittest.TestCase):
    def tearDown(self):
        set_verbose_console(False)

    def _run(self, verbose: bool):
        tmp = tempfile.mkdtemp()
        code_interpreter = MagicMock()
        code_interpreter.execute_code.return_value = ("hello\n", "")
        code_interpreter.extract_code.side_effect = lambda text, *a, **k: "print('hello')"
        safety = MagicMock()
        safety.build_sandbox_context.return_value = MagicMock()

        controller, buf = _make_gemini_controller(
            verbose=verbose, tmp_dir=tmp, code_interpreter=code_interpreter, safety=safety
        )
        with patch("libs.agent.react_controller.call_llm", side_effect=list(_RESPONSES)), \
             patch(
                "libs.agent.actions.coder.call_llm",
                return_value=("```python\nprint('hello')\n```", {"cost": 0.0, "tokens": 2}),
             ), \
             patch(
                "libs.agent.actions.reviewer.call_llm",
                return_value=('{"passed": true, "reason": "ok"}', {"cost": 0.0, "tokens": 2}),
             ):
            final = controller.run("Print hello")
        return controller, final, buf, tmp

    def test_default_run_shows_only_thought_panels(self):
        controller, final, buf, tmp = self._run(verbose=False)
        self.assertFalse(controller.verbose)
        self.assertFalse(is_verbose_console())
        self.assertEqual(final["status"], "COMPLETED")

        joined = buf.getvalue()
        # Every Thought is visible, back-to-back.
        self.assertIn("Write code to print hello", joined)
        self.assertIn("Execute the script", joined)
        self.assertIn("Review the output", joined)
        self.assertIn("Task is done", joined)
        # Action/Observation step noise is suppressed.
        self.assertNotIn("Action (step", joined)
        self.assertNotIn("Observation", joined)

    def test_default_run_still_surfaces_final_result(self):
        """The finish summary is the deliverable, not step noise — it must
        still print even in the default Thought-only quiet view."""
        controller, final, buf, tmp = self._run(verbose=False)
        joined = buf.getvalue()
        self.assertIn("Result", joined)
        self.assertIn("printed hello successfully", joined)

    def test_default_run_preserves_full_trajectory_jsonl_logging(self):
        """Suppressing console Action/Observation panels must NOT remove any
        detail from the on-disk trajectory JSONL used for debugging."""
        controller, final, buf, tmp = self._run(verbose=False)
        log_path = os.path.join(tmp, "agent_react.jsonl")
        self.assertTrue(os.path.exists(log_path))
        with open(log_path, "r", encoding="utf-8") as fh:
            lines = [json.loads(line) for line in fh if line.strip()]
        steps = [entry for entry in lines if entry.get("type") == "step"]
        # Every dispatched action (code/execute/review/finish) is logged with
        # its full observation text, regardless of what the console showed.
        actions_logged = {entry["action"] for entry in steps}
        self.assertIn("execute", actions_logged)
        self.assertIn("finish", actions_logged)
        execute_entry = next(e for e in steps if e["action"] == "execute")
        self.assertIn("hello", execute_entry["observation"])
        summary_entries = [entry for entry in lines if entry.get("type") == "summary"]
        self.assertEqual(len(summary_entries), 1)
        self.assertEqual(summary_entries[0]["status"], "COMPLETED")

    def test_verbose_run_restores_action_and_observation_panels(self):
        controller, final, buf, tmp = self._run(verbose=True)
        self.assertTrue(controller.verbose)
        self.assertTrue(is_verbose_console())
        self.assertEqual(final["status"], "COMPLETED")

        joined = buf.getvalue()
        self.assertIn("Write code to print hello", joined)
        self.assertIn("Action (step", joined)
        self.assertIn("Observation", joined)


class ReActControllerFallbackNoiseGatingTests(unittest.TestCase):
    def tearDown(self):
        set_verbose_console(False)

    def _controller(self, *, verbose: bool, tmp: str) -> ReActController:
        return ReActController(
            model_name="gpt-4o",
            api_key="test",
            code_interpreter=MagicMock(),
            safety_manager=MagicMock(),
            log_path=os.path.join(tmp, "agent_react.jsonl"),
            max_steps=5,
            quiet_ui=True,
            verbose=verbose,
        )

    def test_free_model_fallback_console_line_suppressed_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            controller = self._controller(verbose=False, tmp=tmp)
            with patch("libs.agent.react_controller.console.print") as mock_print:
                controller._on_llm_fallback(
                    {"model": "groq/llama-3.1-8b-instant", "config": "groq-llama-3.1-8b"}
                )
            mock_print.assert_not_called()

    def test_free_model_fallback_console_line_shown_when_verbose(self):
        with tempfile.TemporaryDirectory() as tmp:
            controller = self._controller(verbose=True, tmp=tmp)
            with patch("libs.agent.react_controller.console.print") as mock_print:
                controller._on_llm_fallback(
                    {"model": "groq/llama-3.1-8b-instant", "config": "groq-llama-3.1-8b"}
                )
            mock_print.assert_called_once()
            printed = str(mock_print.call_args[0][0])
            self.assertIn("Free model fallback", printed)


if __name__ == "__main__":
    unittest.main()
