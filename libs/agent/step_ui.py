# -*- coding: utf-8 -*-
"""Gemini-CLI-style step UX: Thinking / Action / Observation with Rich spinners."""

from __future__ import annotations

import logging
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)


class NullStepPresenter:
	"""Silent presenter for tests / structured JSON output."""

	@contextmanager
	def thinking(self, step: int = 0) -> Iterator[None]:
		yield

	@contextmanager
	def acting(self, step: int = 0, action: str = "") -> Iterator[None]:
		yield

	@contextmanager
	def searching(self, query: str = "") -> Iterator[None]:
		yield

	def show_thought(self, step: int, thought: str) -> None:
		return None

	def show_action(self, step: int, action: str, action_input: Any = None) -> None:
		return None

	def show_observation(self, step: int, observation: str) -> None:
		return None

	def show_status(self, message: str) -> None:
		return None


class PlainStepPresenter:
	"""Compact one-line Thought / Action / Observation (legacy ReAct look)."""

	def __init__(self, console: Any = None):
		self.console = console or _default_console()

	@contextmanager
	def thinking(self, step: int = 0) -> Iterator[None]:
		yield

	@contextmanager
	def acting(self, step: int = 0, action: str = "") -> Iterator[None]:
		yield

	@contextmanager
	def searching(self, query: str = "") -> Iterator[None]:
		yield

	def show_thought(self, step: int, thought: str) -> None:
		text = (thought or "").replace("\n", " ").strip()
		if len(text) > 160:
			text = text[:157] + "..."
		self.console.print(f"[bold blue]Step {step}[/bold blue] Thought: {text}")

	def show_action(self, step: int, action: str, action_input: Any = None) -> None:
		self.console.print(f"[bold cyan]Action:[/bold cyan] {action}")

	def show_observation(self, step: int, observation: str) -> None:
		text = (observation or "").replace("\n", " ").strip()
		if len(text) > 200:
			text = text[:197] + "..."
		self.console.print(f"[dim]Observation: {text}[/dim]\n")

	def show_status(self, message: str) -> None:
		self.console.print(f"[dim]{message}[/dim]")


class GeminiStepPresenter:
	"""Rich spinner + labeled Thought → Action → Observation blocks (Gemini-CLI feel)."""

	def __init__(self, console: Any = None, *, spinner: str = "dots"):
		self.console = console or _default_console()
		self.spinner = spinner

	def _status(self, label: str):
		"""Return a Rich Status context manager, or nullcontext if unavailable."""
		console = self.console
		if console is None or not hasattr(console, "status"):
			return nullcontext()
		try:
			return console.status(label, spinner=self.spinner)
		except TypeError:
			# Some mocks / consoles accept only the message
			try:
				return console.status(label)
			except Exception:
				return nullcontext()
		except Exception:
			return nullcontext()

	@contextmanager
	def thinking(self, step: int = 0) -> Iterator[None]:
		label = f"[bold cyan]Thinking…[/bold cyan] (step {step})" if step else "[bold cyan]Thinking…[/bold cyan]"
		with self._status(label):
			yield

	@contextmanager
	def acting(self, step: int = 0, action: str = "") -> Iterator[None]:
		action = action or "work"
		label = f"[bold yellow]Executing {action}…[/bold yellow]"
		if step:
			label = f"[bold yellow]Executing {action}…[/bold yellow] (step {step})"
		with self._status(label):
			yield

	@contextmanager
	def searching(self, query: str = "") -> Iterator[None]:
		q = (query or "").strip()
		suffix = f": {q[:60]}" if q else ""
		with self._status(f"[bold magenta]Searching…{suffix}[/bold magenta]"):
			yield

	def show_thought(self, step: int, thought: str) -> None:
		text = (thought or "").strip() or "(empty)"
		# Prefer a Panel when Rich is available; fall back to labeled print.
		try:
			from rich.panel import Panel

			title = f"Thought · step {step}" if step else "Thought"
			# Avoid Markdown parsing surprises on free-form agent text
			self.console.print(
				Panel(text, title=f"[bold blue]{title}[/bold blue]", border_style="blue", expand=False)
			)
		except Exception:
			preview = text.replace("\n", " ")
			if len(preview) > 240:
				preview = preview[:237] + "..."
			self.console.print(f"[bold blue]Thought (step {step}):[/bold blue] {preview}")

	def show_action(self, step: int, action: str, action_input: Any = None) -> None:
		detail = ""
		if action_input is not None:
			try:
				import json

				if isinstance(action_input, (dict, list)):
					detail = json.dumps(action_input, default=str)
				else:
					detail = str(action_input)
			except Exception:
				detail = str(action_input)
			if len(detail) > 120:
				detail = detail[:117] + "..."
		line = f"[bold cyan]Action (step {step}):[/bold cyan] {action}"
		if detail:
			line += f"  [dim]{detail}[/dim]"
		self.console.print(line)

	def show_observation(self, step: int, observation: str) -> None:
		text = (observation or "").strip() or "(empty)"
		try:
			from rich.panel import Panel

			preview = text if len(text) <= 800 else text[:797] + "..."
			self.console.print(
				Panel(
					preview,
					title=f"[dim]Observation · step {step}[/dim]",
					border_style="dim",
					expand=False,
				)
			)
		except Exception:
			preview = text.replace("\n", " ")
			if len(preview) > 200:
				preview = preview[:197] + "..."
			self.console.print(f"[dim]Observation (step {step}): {preview}[/dim]\n")

	def show_status(self, message: str) -> None:
		self.console.print(f"[cyan]{message}[/cyan]")


def make_step_presenter(
	*,
	gemini_style: bool = False,
	quiet: bool = False,
	console: Any = None,
) -> Any:
	"""Factory: quiet → Null; gemini_style → Gemini; else Plain."""
	if quiet:
		return NullStepPresenter()
	if gemini_style:
		return GeminiStepPresenter(console=console)
	return PlainStepPresenter(console=console)


def _default_console():
	try:
		from rich.console import Console

		return Console()
	except Exception:
		return _FallbackConsole()


class _FallbackConsole:
	def print(self, *args, **kwargs):
		print(*args)

	def status(self, *args, **kwargs):
		return nullcontext()
