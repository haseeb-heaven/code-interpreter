# -*- coding: utf-8 -*-
"""Gemini-CLI-inspired startup banner, tips, and status bar for the agentic REPL.

Renders a blocky "INTERPRETER" wordmark (blue -> purple -> pink gradient),
a "Tips for getting started" section, and a persistent-feeling footer status
bar (cwd / sandbox mode / confirm mode), matching the visual language of
Google's Gemini CLI but branded for this project.

All rendering helpers are split from small, independently-testable pure
functions (bitmap/gradient/text builders) so unit tests can assert on
*structure* (row counts, substrings) without depending on exact ANSI output.
Every renderer degrades gracefully: Rich/Unicode failures fall back to
plain ASCII-safe text instead of raising, matching ``libs/onboarding.py``'s
Windows cp1252-safe printing convention.
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Blocky 5x6 bitmap font — only the letters needed for "INTERPRETER".
# '#' = filled pixel, '.' = empty. Each glyph row must stay 5 chars wide.
# --------------------------------------------------------------------------
_FONT_WIDTH = 5
_FONT_HEIGHT = 6

_FONT: Dict[str, Tuple[str, ...]] = {
	"I": (".###.", ".###.", ".###.", ".###.", ".###.", ".###."),
	"N": ("#...#", "##..#", "#.#.#", "#.#.#", "#..##", "#...#"),
	"T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#.."),
	"E": ("#####", "#....", "####.", "#....", "#....", "#####"),
	"R": ("####.", "#...#", "####.", "#..#.", "#...#", "#...#"),
	"P": ("####.", "#...#", "####.", "#....", "#....", "#...."),
}

# Small right-pointing chevron, same cell size, printed left of the wordmark.
_CHEVRON: Tuple[str, ...] = ("#....", ".#...", "..#..", "..#..", ".#...", "#....")

# "INTERPRETER" split across two rows so it stays inside ~80 columns while
# keeping the chunky, wide pixel-art look from the reference screenshot.
BANNER_LINES: Tuple[str, str] = ("INTER", "PRETER")

# Blue -> purple -> pink, approximating the Gemini CLI wordmark gradient.
_GRADIENT_STOPS: Tuple[Tuple[int, int, int], ...] = (
	(59, 130, 246),   # blue
	(168, 85, 247),   # purple
	(236, 72, 153),   # pink
)


def _glyph_rows(char: str) -> Tuple[str, ...]:
	"""Return the bitmap rows for one character, or a blank cell if unknown."""
	return _FONT.get(char.upper(), ("." * _FONT_WIDTH,) * _FONT_HEIGHT)


def word_bitmap_rows(word: str, *, gap: int = 1, prefix: Optional[Sequence[str]] = None) -> List[str]:
	"""Compose a word's per-row bitmap strings from the block font.

	Returns exactly ``_FONT_HEIGHT`` strings. Unknown characters render as a
	blank cell rather than raising, so this never crashes on unexpected input.
	"""
	if not word:
		return ["" for _ in range(_FONT_HEIGHT)]
	glyphs = [_glyph_rows(ch) for ch in word]
	gap_col = "." * max(gap, 0)
	rows = [gap_col.join(g[r] for g in glyphs) for r in range(_FONT_HEIGHT)]
	if prefix:
		rows = [f"{prefix[r]}{gap_col}{rows[r]}" for r in range(_FONT_HEIGHT)]
	return rows


def scale_rows(rows: Sequence[str], pixel_width: int = 2) -> List[str]:
	"""Widen each bitmap column by ``pixel_width`` chars for squarer pixels."""
	if pixel_width <= 1:
		return list(rows)
	return ["".join(ch * pixel_width for ch in row) for row in rows]


def gradient_color_at(t: float) -> Tuple[int, int, int]:
	"""Interpolate an RGB color at position ``t`` (0..1) across the brand gradient."""
	t = max(0.0, min(1.0, t))
	segments = len(_GRADIENT_STOPS) - 1
	scaled = t * segments
	idx = min(int(scaled), segments - 1)
	local_t = scaled - idx
	c0, c1 = _GRADIENT_STOPS[idx], _GRADIENT_STOPS[idx + 1]
	return tuple(round(c0[i] + (c1[i] - c0[i]) * local_t) for i in range(3))  # type: ignore[return-value]


def _hex_color(rgb: Tuple[int, int, int]) -> str:
	return "#{:02x}{:02x}{:02x}".format(*rgb)


_UNICODE_PROBE = "\u2588\u2713\u2726\u25b6"  # block, check, star, play — the glyphs we might print


def supports_unicode(console) -> bool:
	"""Best-effort check for whether ``console`` can safely print our glyphs.

	Must be checked *before* printing, not just caught after: Rich's legacy
	Windows console path writes through the raw codepage rather than
	ANSI/UTF-8, and an encode failure there can leave Rich's internal write
	buffer in a state that corrupts *later*, otherwise-plain prints too.
	"""
	try:
		if getattr(console, "legacy_windows", False):
			return False
		stream = getattr(console, "file", None)
		encoding = getattr(stream, "encoding", None) if stream is not None else None
		if encoding:
			_UNICODE_PROBE.encode(encoding)
		return True
	except Exception:
		return False


def _default_console():
	try:
		from rich.console import Console

		return Console()
	except Exception:
		return _FallbackConsole()


class _FallbackConsole:
	"""Minimal console used when Rich is unavailable (mirrors step_ui.py)."""

	width = 80

	def print(self, *args, **kwargs):
		print(*args)


def _safe_print(console, renderable, ascii_fallback: str) -> None:
	"""Print ``renderable``; fall back to plain ASCII text on encode errors.

	Mirrors the Windows cp1252-safe pattern already used by
	``libs/onboarding.py`` so glyph-heavy output never crashes narrow consoles.
	Always forces ``overflow="crop", no_wrap=True`` so a wrong width reading
	degrades to a clipped-but-legible line instead of wraparound corruption.
	"""
	try:
		console.print(renderable, overflow="crop", no_wrap=True)
	except UnicodeEncodeError:
		logger.debug("Unicode render failed; using ASCII-safe fallback")
		try:
			console.print(ascii_fallback, overflow="crop", no_wrap=True)
		except Exception:
			print(ascii_fallback)
	except Exception as exc:
		logger.debug("Console print failed (%s); using ASCII-safe fallback", exc)
		try:
			console.print(ascii_fallback, overflow="crop", no_wrap=True)
		except Exception:
			print(ascii_fallback)


def render_wordmark_text(word: str, *, pixel_width: int = 2, with_chevron: bool = False):
	"""Build a Rich ``Text`` for one bitmap-font word with a per-column gradient."""
	from rich.text import Text

	prefix_rows = _CHEVRON if with_chevron else None
	rows = word_bitmap_rows(word, prefix=prefix_rows)
	scaled = scale_rows(rows, pixel_width=pixel_width)
	width = len(scaled[0]) if scaled else 0

	text = Text()
	for row_idx, row in enumerate(scaled):
		for col_idx, cell in enumerate(row):
			if cell == "#":
				t = col_idx / max(width - 1, 1)
				text.append("\u2588", style=_hex_color(gradient_color_at(t)))
			else:
				text.append(" ")
		if row_idx != len(scaled) - 1:
			text.append("\n")
	return text


def render_banner(console=None, *, width: Optional[int] = None) -> None:
	"""Print the blocky INTERPRETER wordmark, sized to fit the terminal width."""
	console = console or _default_console()
	ascii_fallback = "> INTERPRETER"

	# Legacy cp1252 Windows consoles can't safely print block-drawing glyphs —
	# and a failed attempt there can corrupt Rich's write buffer for later
	# prints too, so this must be decided *before* any Unicode print attempt.
	if not supports_unicode(console):
		_safe_print(console, f"[bold magenta]{ascii_fallback}[/bold magenta]", ascii_fallback)
		return

	try:
		term_width = int(width if width is not None else getattr(console, "width", 80) or 80)
		try:
			term_width = min(term_width, shutil.get_terminal_size(fallback=(80, 24)).columns)
		except Exception:
			pass
	except (TypeError, ValueError):
		term_width = 80

	# Widest scaled row is ~70 cols at pixel_width=2, ~35 at pixel_width=1.
	if term_width >= 72:
		pixel_width = 2
	elif term_width >= 36:
		pixel_width = 1
	else:
		pixel_width = 0  # Too narrow for the block font — plain text fallback.

	if pixel_width == 0:
		_safe_print(console, f"[bold magenta]{ascii_fallback}[/bold magenta]", ascii_fallback)
		return

	try:
		line1 = render_wordmark_text(BANNER_LINES[0], pixel_width=pixel_width, with_chevron=True)
		line2 = render_wordmark_text(BANNER_LINES[1], pixel_width=pixel_width)
		_safe_print(console, line1, ascii_fallback)
		_safe_print(console, line2, "")
	except Exception as exc:
		logger.debug("Banner render failed entirely, using plain fallback: %s", exc)
		_safe_print(console, f"[bold magenta]{ascii_fallback}[/bold magenta]", ascii_fallback)


def render_persistent_banner(console=None, *, width: Optional[int] = None) -> None:
	"""Print just the INTERPRETER wordmark (no tips/footer).

	Thin wrapper around ``render_banner`` used by every genuinely interactive
	entry point (classic ``--cli`` REPL, ``--agentic``, the autonomous
	``--yolo`` loop, and the arrow-key TUI wizard) so the banner shows at
	session start without duplicating banner-print call sites, and by
	``UtilityManager.clear_screen`` so the banner redraws immediately after
	any explicit screen clear — keeping it visually "pinned" to the top.
	"""
	render_banner(console, width=width)


# --------------------------------------------------------------------------
# Tips
# --------------------------------------------------------------------------
TIPS_HEADER = "Tips for getting started:"


def tips_lines() -> List[str]:
	"""Return the REPL's onboarding tips, reflecting real slash commands."""
	return [
		"Describe a task in plain English - code, data, files, or shell commands.",
		"Be specific for the best results (mention filenames, languages, formats).",
		"/free for zero-cost models, /model <name> to switch, /settings for options.",
		"/help for all commands, /exit to leave the REPL.",
	]


def render_tips(console=None) -> None:
	console = console or _default_console()
	try:
		console.print(f"[bold]{TIPS_HEADER}[/bold]")
		for idx, line in enumerate(tips_lines(), start=1):
			console.print(f"[dim]{idx}. {line}[/dim]")
	except Exception as exc:
		logger.debug("Tips render failed, using plain print: %s", exc)
		print(TIPS_HEADER)
		for idx, line in enumerate(tips_lines(), start=1):
			print(f"{idx}. {line}")


# --------------------------------------------------------------------------
# Footer status bar (cwd | sandbox mode | confirm mode)
# --------------------------------------------------------------------------
def shorten_cwd(path: Optional[str] = None, *, home: Optional[str] = None) -> str:
	"""Collapse the home directory prefix to ``~`` (Gemini-CLI-style footer)."""
	try:
		raw = path or os.getcwd()
		home_dir = home if home is not None else os.path.expanduser("~")
		if home_dir and raw.startswith(home_dir):
			suffix = raw[len(home_dir):].lstrip("\\/")
			return "~" if not suffix else f"~{os.sep}{suffix}"
		return raw
	except Exception as exc:
		logger.debug("Could not shorten cwd: %s", exc)
		return path or ""


def footer_parts(cwd: Optional[str], sandboxed: bool, auto_yes: bool) -> Tuple[str, str, str]:
	"""Return (left, center, right) footer strings — pure, easily testable."""
	left = shorten_cwd(cwd)
	center = "sandboxed (SAFE MODE)" if sandboxed else "no sandbox - see --no-sandbox docs"
	right = "auto (--yes)" if auto_yes else "manual confirm"
	return left, center, right


def render_footer(console=None, *, cwd: Optional[str] = None, sandboxed: bool = True,
				   auto_yes: bool = False, width: Optional[int] = None) -> None:
	"""Print a three-part status line: cwd (left) | sandbox (center) | mode (right)."""
	console = console or _default_console()
	left, center, right = footer_parts(cwd, sandboxed, auto_yes)
	plain = f"{left}  |  {center}  |  {right}"
	try:
		from rich.table import Table

		grid = Table.grid(expand=True, padding=0)
		grid.add_column(justify="left", ratio=1)
		grid.add_column(justify="center", ratio=1)
		grid.add_column(justify="right", ratio=1)
		grid.add_row(f"[dim]{left}[/dim]", f"[dim]{center}[/dim]", f"[dim]{right}[/dim]")
		_safe_print(console, grid, plain)
	except Exception as exc:
		logger.debug("Footer render failed, using plain line: %s", exc)
		_safe_print(console, plain, plain)


# --------------------------------------------------------------------------
# Context metadata line (Gemini CLI's "Using: N GEMINI.md files | M MCP
# servers"). Only shown when there is a real, non-fabricated count to report.
# --------------------------------------------------------------------------
def context_metadata_line(*, actions_count: Optional[int] = None,
						   session_turns: Optional[int] = None) -> Optional[str]:
	"""Build the dim metadata line, or ``None`` when there is nothing real to show."""
	parts: List[str] = []
	if actions_count:
		noun = "action" if actions_count == 1 else "actions"
		parts.append(f"{actions_count} agent {noun} (code, execute, review, debug)")
	if session_turns:
		noun = "turn" if session_turns == 1 else "turns"
		parts.append(f"session memory: {session_turns} {noun}")
	if not parts:
		return None
	return "Using: " + " | ".join(parts)


def render_context_line(console=None, *, actions_count: Optional[int] = None,
						 session_turns: Optional[int] = None) -> None:
	console = console or _default_console()
	line = context_metadata_line(actions_count=actions_count, session_turns=session_turns)
	if not line:
		return
	try:
		console.print(f"[dim]{line}[/dim]")
	except Exception as exc:
		logger.debug("Context line render failed, using plain print: %s", exc)
		print(line)


# --------------------------------------------------------------------------
# Composite entry points used by the REPL
# --------------------------------------------------------------------------
def render_startup_screen(console=None, *, width: Optional[int] = None) -> None:
	"""Banner + tips, printed once when the Gemini-style REPL starts."""
	console = console or _default_console()
	render_banner(console, width=width)
	console.print("")
	render_tips(console)


def render_status_bar(console=None, *, cwd: Optional[str] = None, sandboxed: bool = True,
					   auto_yes: bool = False, actions_count: Optional[int] = None,
					   session_turns: Optional[int] = None, width: Optional[int] = None) -> None:
	"""Context line + footer, re-printed before each prompt (best-effort "persistent" footer)."""
	console = console or _default_console()
	render_context_line(console, actions_count=actions_count, session_turns=session_turns)
	render_footer(console, cwd=cwd, sandboxed=sandboxed, auto_yes=auto_yes, width=width)
