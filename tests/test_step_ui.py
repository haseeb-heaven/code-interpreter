# -*- coding: utf-8 -*-
"""Unit tests for Gemini-style step UX helpers."""

from __future__ import annotations

import io
import unittest
from unittest.mock import MagicMock

from libs.agent.step_ui import (
	GeminiStepPresenter,
	NullStepPresenter,
	PlainStepPresenter,
	make_step_presenter,
)


class TestStepPresenterFactory(unittest.TestCase):
	def test_gemini_style_returns_gemini_presenter(self):
		p = make_step_presenter(gemini_style=True, quiet=False)
		self.assertIsInstance(p, GeminiStepPresenter)

	def test_plain_by_default(self):
		p = make_step_presenter(gemini_style=False, quiet=False)
		self.assertIsInstance(p, PlainStepPresenter)

	def test_quiet_returns_null(self):
		p = make_step_presenter(gemini_style=True, quiet=True)
		self.assertIsInstance(p, NullStepPresenter)

	def test_gemini_style_defaults_to_thought_only(self):
		p = make_step_presenter(gemini_style=True, quiet=False)
		self.assertFalse(p.verbose)

	def test_verbose_flag_passed_through_to_gemini_presenter(self):
		p = make_step_presenter(gemini_style=True, quiet=False, verbose=True)
		self.assertIsInstance(p, GeminiStepPresenter)
		self.assertTrue(p.verbose)


class TestGeminiStepPresenter(unittest.TestCase):
	def test_default_is_thought_only_suppresses_action_and_observation(self):
		"""New default (verbose=False): only the Thought panel renders back-to-back;
		Action/Observation panels must not be printed at all."""
		from rich.console import Console

		buf = io.StringIO()
		console = Console(file=buf, force_terminal=True, width=100, color_system=None)
		presenter = GeminiStepPresenter(console=console)
		self.assertFalse(presenter.verbose)

		with presenter.thinking(step=1):
			pass
		presenter.show_thought(1, "I need ffmpeg to trim the video")
		presenter.show_action(1, "execute", {"language": "python"})
		with presenter.acting(step=1, action="execute"):
			pass
		presenter.show_observation(1, "ERROR: ffmpeg not found")

		joined = buf.getvalue()
		self.assertIn("Thought", joined)
		self.assertIn("ffmpeg", joined)
		self.assertNotIn("Action", joined)
		self.assertNotIn("Observation", joined)
		self.assertNotIn("ffmpeg not found", joined)

	def test_default_never_calls_console_print_for_action_or_observation(self):
		"""Assert the underlying Console.print call itself is skipped for
		Action/Observation in the default (non-verbose) mode, not merely that
		its rendered text is absent."""
		console = MagicMock()
		presenter = GeminiStepPresenter(console=console)
		presenter.show_action(1, "execute", {"language": "python"})
		presenter.show_observation(1, "ERROR: ffmpeg not found")
		console.print.assert_not_called()

		presenter.show_thought(1, "plan the trim")
		self.assertEqual(console.print.call_count, 1)

	def test_verbose_mode_restores_full_thought_action_observation_sequence(self):
		"""``verbose=True`` (``--verbose``/``-V`` or ``/verbose``) restores the
		full legacy interleaved Thought -> Action -> Observation display."""
		from rich.console import Console

		buf = io.StringIO()
		console = Console(file=buf, force_terminal=True, width=100, color_system=None)
		presenter = GeminiStepPresenter(console=console, verbose=True)
		self.assertTrue(presenter.verbose)
		with presenter.thinking(step=1):
			pass
		presenter.show_thought(1, "I need ffmpeg to trim the video")
		presenter.show_action(1, "execute", {"language": "python"})
		with presenter.acting(step=1, action="execute"):
			pass
		presenter.show_observation(1, "ERROR: ffmpeg not found")

		joined = buf.getvalue()
		self.assertIn("Thought", joined)
		self.assertIn("ffmpeg", joined)
		self.assertIn("Action", joined)
		self.assertIn("execute", joined)
		self.assertIn("Observation", joined)

	def test_show_result_always_renders_regardless_of_verbose(self):
		"""The final task result/summary must surface even in the default
		Thought-only quiet view — it's the deliverable, not step noise."""
		from rich.console import Console

		buf = io.StringIO()
		console = Console(file=buf, force_terminal=True, width=100, color_system=None)
		presenter = GeminiStepPresenter(console=console, verbose=False)
		presenter.show_result("chart saved to sales.png")
		joined = buf.getvalue()
		self.assertIn("Result", joined)
		self.assertIn("chart saved to sales.png", joined)

	def test_searching_status_label(self):
		console = MagicMock()
		status_cm = MagicMock()
		status_cm.__enter__ = MagicMock(return_value=status_cm)
		status_cm.__exit__ = MagicMock(return_value=False)
		console.status.return_value = status_cm
		presenter = GeminiStepPresenter(console=console)
		with presenter.searching("ffmpeg install windows"):
			pass
		args = console.status.call_args
		label = str(args[0][0]) if args and args[0] else str(args)
		self.assertIn("Search", label)

	def test_null_presenter_is_noop(self):
		p = NullStepPresenter()
		with p.thinking(1):
			pass
		with p.acting(1, "code"):
			pass
		with p.searching("q"):
			pass
		p.show_thought(1, "x")
		p.show_action(1, "code", {})
		p.show_observation(1, "ok")
		p.show_result("ok")
		p.show_observation(1, "print('hi')", action="code")
		p.show_responding_with("gemini-2.5-flash")
		p.show_finish(1, "done")

	def test_code_action_renders_line_numbered_panel(self):
		from rich.console import Console

		buf = io.StringIO()
		console = Console(file=buf, force_terminal=True, width=100, color_system=None)
		presenter = GeminiStepPresenter(console=console, verbose=True)
		presenter.show_observation(3, "print('Hello, world!')", action="code")

		joined = buf.getvalue()
		self.assertIn("Code", joined)
		self.assertIn("print", joined)
		self.assertIn("1", joined)  # Syntax line-number gutter

	def test_show_responding_with_mentions_model(self):
		from rich.console import Console

		buf = io.StringIO()
		console = Console(file=buf, force_terminal=True, width=100, color_system=None)
		presenter = GeminiStepPresenter(console=console)
		presenter.show_responding_with("gemini-2.5-flash")
		self.assertIn("Responding with gemini-2.5-flash", buf.getvalue())

	def test_show_finish_prints_summary(self):
		from rich.console import Console

		buf = io.StringIO()
		console = Console(file=buf, force_terminal=True, width=100, color_system=None)
		presenter = GeminiStepPresenter(console=console)
		presenter.show_finish(2, "hello.py has been created")
		self.assertIn("hello.py has been created", buf.getvalue())

	def test_ascii_icons_used_for_legacy_windows_console(self):
		console = type("C", (), {"legacy_windows": True, "print": lambda self, *a, **k: None})()
		presenter = GeminiStepPresenter(console=console)
		self.assertEqual(presenter._action_icons["code"], "*")
		self.assertEqual(presenter._assistant_icon, "*")

	def test_unicode_icons_used_for_utf8_console(self):
		from rich.console import Console

		console = Console(file=io.StringIO(), force_terminal=True, legacy_windows=False)
		presenter = GeminiStepPresenter(console=console)
		self.assertNotEqual(presenter._action_icons["finish"], "OK")


class TestPlainStepPresenter(unittest.TestCase):
	def test_prints_compact_lines(self):
		printed = []
		console = MagicMock()
		console.print = lambda *a, **k: printed.append(" ".join(str(x) for x in a))
		p = PlainStepPresenter(console=console)
		p.show_thought(2, "plan the trim")
		p.show_action(2, "code", {})
		p.show_observation(2, "SUCCESS")
		p.show_result("chart saved to sales.png")
		joined = "\n".join(printed)
		self.assertIn("Thought", joined)
		self.assertIn("Action", joined)
		self.assertIn("Observation", joined)
		self.assertIn("Result", joined)
		self.assertIn("chart saved to sales.png", joined)


if __name__ == "__main__":
	unittest.main()
