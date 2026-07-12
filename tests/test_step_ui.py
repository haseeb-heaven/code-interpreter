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


class TestGeminiStepPresenter(unittest.TestCase):
	def test_thought_action_observation_sequence(self):
		from rich.console import Console

		buf = io.StringIO()
		console = Console(file=buf, force_terminal=True, width=100, color_system=None)
		presenter = GeminiStepPresenter(console=console)
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


class TestPlainStepPresenter(unittest.TestCase):
	def test_prints_compact_lines(self):
		printed = []
		console = MagicMock()
		console.print = lambda *a, **k: printed.append(" ".join(str(x) for x in a))
		p = PlainStepPresenter(console=console)
		p.show_thought(2, "plan the trim")
		p.show_action(2, "code", {})
		p.show_observation(2, "SUCCESS")
		joined = "\n".join(printed)
		self.assertIn("Thought", joined)
		self.assertIn("Action", joined)
		self.assertIn("Observation", joined)


if __name__ == "__main__":
	unittest.main()
