# -*- coding: utf-8 -*-
"""Gemini-CLI-style step UX: Thinking / Action / Observation with Rich spinners."""

from __future__ import annotations

import logging
from contextlib import contextmanager, nullcontext
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)

# Icons for each ReAct action, echoing the reference Gemini CLI's checkmark /
# glyph-prefixed tool-call rows. Two variants: Unicode for modern terminals,
# plain ASCII for legacy cp1252 Windows consoles (see ``_icons_for`` below —
# a failed Unicode write there can corrupt Rich's buffer for later prints).
_ACTION_ICONS_UNICODE = {
	"code": "\u270e",     # lower left pencil — "writing" a file/snippet
	"execute": "\u25b6",  # play — running code
	"review": "\U0001f50e",
	"debug": "\U0001f6e0",
	"finish": "\u2713",   # check mark
}
_ACTION_ICONS_ASCII = {
	"code": "*",
	"execute": ">",
	"review": "?",
	"debug": "!",
	"finish": "OK",
}
_ASSISTANT_ICON_UNICODE = "\u2726"  # four pointed star, mirrors Gemini CLI's response glyph
_ASSISTANT_ICON_ASCII = "*"


def _icons_for(console) -> Any:
	"""Return (action_icons, assistant_icon) matched to the console's Unicode support."""
	try:
		from libs.agent.gemini_ui import supports_unicode

		if supports_unicode(console):
			return _ACTION_ICONS_UNICODE, _ASSISTANT_ICON_UNICODE
	except Exception as exc:
		logger.debug("Unicode support probe failed (%s); using ASCII icons", exc)
	return _ACTION_ICONS_ASCII, _ASSISTANT_ICON_ASCII


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

	def show_observation(self, step: int, observation: str, action: Optional[str] = None) -> None:
		return None

	def show_status(self, message: str) -> None:
		return None

	def show_responding_with(self, model_name: str) -> None:
		return None

	def show_finish(self, step: int, summary: str) -> None:
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

	def show_observation(self, step: int, observation: str, action: Optional[str] = None) -> None:
		text = (observation or "").replace("\n", " ").strip()
		if len(text) > 200:
			text = text[:197] + "..."
		self.console.print(f"[dim]Observation: {text}[/dim]\n")

	def show_status(self, message: str) -> None:
		self.console.print(f"[dim]{message}[/dim]")

	def show_responding_with(self, model_name: str) -> None:
		self.console.print(f"[dim]Responding with {model_name}[/dim]")

	def show_finish(self, step: int, summary: str) -> None:
		text = (summary or "Finished").strip()
		self.console.print(f"[bold green]Done (step {step}):[/bold green] {text}")


class GeminiStepPresenter:
	"""Rich spinner + labeled Thought → Action → Observation blocks (Gemini-CLI feel)."""

	def __init__(self, console: Any = None, *, spinner: str = "dots"):
		self.console = console or _default_console()
		self.spinner = spinner
		self._action_icons, self._assistant_icon = _icons_for(self.console)

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

	def _print_safe(self, renderable: Any, ascii_fallback: str) -> None:
		"""Print ``renderable``, degrading to plain ASCII text on encode errors."""
		try:
			self.console.print(renderable)
		except Exception as exc:
			logger.debug("Rich render failed (%s); using ASCII-safe fallback", exc)
			try:
				self.console.print(ascii_fallback)
			except Exception:
				print(ascii_fallback)

	@contextmanager
	def thinking(self, step: int = 0) -> Iterator[None]:
		label = f"[bold cyan]Thinking...[/bold cyan] (step {step})" if step else "[bold cyan]Thinking...[/bold cyan]"
		with self._status(label):
			yield

	@contextmanager
	def acting(self, step: int = 0, action: str = "") -> Iterator[None]:
		action = action or "work"
		icon = self._action_icons.get(action, "")
		label = f"[bold yellow]{icon} Executing {action}...[/bold yellow]".strip()
		if step:
			label = f"{label} (step {step})"
		with self._status(label):
			yield

	@contextmanager
	def searching(self, query: str = "") -> Iterator[None]:
		q = (query or "").strip()
		suffix = f": {q[:60]}" if q else ""
		with self._status(f"[bold magenta]Searching...{suffix}[/bold magenta]"):
			yield

	def show_thought(self, step: int, thought: str) -> None:
		text = (thought or "").strip() or "(empty)"
		# Prefer a Panel when Rich is available; fall back to labeled print.
		try:
			from rich.panel import Panel

			title = f"Thought - step {step}" if step else "Thought"
			# Avoid Markdown parsing surprises on free-form agent text
			self._print_safe(
				Panel(text, title=f"[bold blue]{title}[/bold blue]", border_style="blue", expand=False),
				f"Thought (step {step}): {text}",
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
		icon = self._action_icons.get(action, "")
		prefix = f"{icon} " if icon else ""
		line = f"[bold cyan]{prefix}Action (step {step}):[/bold cyan] {action}"
		if detail:
			line += f"  [dim]{detail}[/dim]"
		self._print_safe(line, f"Action (step {step}): {action} {detail}".rstrip())

	def show_observation(self, step: int, observation: str, action: Optional[str] = None) -> None:
		text = (observation or "").strip() or "(empty)"
		if action == "code":
			self._show_code_panel(step, text)
			return
		try:
			from rich.panel import Panel

			preview = text if len(text) <= 800 else text[:797] + "..."
			icon = self._action_icons.get(action, "") if action else ""
			title = f"[dim]{icon} Observation - step {step}[/dim]".strip()
			self._print_safe(
				Panel(preview, title=title, border_style="dim", expand=False),
				f"Observation (step {step}): {preview}",
			)
		except Exception:
			preview = text.replace("\n", " ")
			if len(preview) > 200:
				preview = preview[:197] + "..."
			self.console.print(f"[dim]Observation (step {step}): {preview}[/dim]\n")

	def _show_code_panel(self, step: int, code: str) -> None:
		"""WriteFile-style bordered panel: checkmark header + line-numbered code."""
		preview = code if len(code) <= 4000 else code[:3997] + "..."
		try:
			from rich.panel import Panel
			from rich.syntax import Syntax

			body = Syntax(preview, "python", theme="ansi_dark", line_numbers=True, word_wrap=True)
			check = self._action_icons.get("finish", "")
			title = f"[bold green]{check} Code[/bold green] - step {step}".replace("  ", " ")
			self._print_safe(
				Panel(body, title=title, border_style="green", expand=False),
				f"Code (step {step}):\n{preview}",
			)
		except Exception as exc:
			logger.debug("Syntax-highlighted code panel failed (%s); using plain text", exc)
			self.console.print(f"[dim]Code (step {step}):[/dim]\n{preview}")

	def show_status(self, message: str) -> None:
		icon = self._assistant_icon
		self._print_safe(f"[cyan]{icon} {message}[/cyan]", f"{icon} {message}")

	def show_responding_with(self, model_name: str) -> None:
		"""Dim italic status line, matching Gemini CLI's "Responding with <model>"."""
		text = f"Responding with {model_name}"
		self._print_safe(f"[dim italic]{text}[/dim italic]", text)

	def show_finish(self, step: int, summary: str) -> None:
		"""Assistant-style closing message, prefixed with the response glyph."""
		text = (summary or "Finished").strip()
		icon = self._assistant_icon
		self._print_safe(f"[magenta]{icon}[/magenta] {text}", f"{icon} {text}")


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
