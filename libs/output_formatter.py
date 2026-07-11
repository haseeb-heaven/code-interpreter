# -*- coding: utf-8 -*-
"""Structured output emission for scripting, piping, and CI (#219)."""

from __future__ import annotations

import json
import logging
import re
import sys
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class OutputFormat(str, Enum):
	PLAIN = "plain"
	JSON = "json"
	MARKDOWN = "markdown"


class OutputFormatter:
	"""
	Handles final result emission in plain, JSON, or Markdown format.

	When ``--output-format`` is omitted, non-TTY (piped) stdout auto-selects JSON
	and disables color. An explicit ``--output-format plain`` keeps plain output
	even when piped.
	"""

	def __init__(
		self,
		fmt: OutputFormat = OutputFormat.PLAIN,
		no_color: bool = False,
		*,
		isatty: Optional[bool] = None,
	):
		tty = sys.stdout.isatty() if isatty is None else bool(isatty)
		self.fmt = fmt if isinstance(fmt, OutputFormat) else OutputFormat(fmt)
		self.no_color = bool(no_color) or not tty
		self._isatty = tty

	@property
	def is_structured(self) -> bool:
		"""True when stdout should carry machine-oriented output only."""
		return self.fmt in (OutputFormat.JSON, OutputFormat.MARKDOWN)

	def apply_env_suppression(self) -> None:
		"""Hint Rich / libraries to drop decorations (spinners, colors)."""
		import os

		if self.is_structured or self.no_color:
			os.environ["CI"] = "1"
			os.environ["NO_COLOR"] = "1"

	def emit(
		self,
		result_text: str,
		code: Optional[str] = None,
		execution_output: Optional[str] = None,
		error: Optional[str] = None,
		status: str = "success",
		*,
		language: str = "python",
		file: Any = None,
	) -> None:
		"""
		Emit the final result in the configured format.

		Args:
			result_text: The LLM's response / explanation text
			code: The generated/executed code block (if any)
			execution_output: Stdout from code execution (if any)
			error: Error message if something failed
			status: 'success' | 'error' | 'partial'
			language: Language hint for Markdown fenced code blocks
			file: Optional stream (defaults to stdout); used by tests
		"""
		out = file if file is not None else sys.stdout
		if self.fmt == OutputFormat.JSON:
			self._emit_json(result_text, code, execution_output, error, status, file=out)
		elif self.fmt == OutputFormat.MARKDOWN:
			self._emit_markdown(result_text, code, execution_output, language=language, file=out)
		else:
			self._emit_plain(result_text)

	def _emit_json(self, result_text, code, execution_output, error, status, *, file):
		payload = {
			"status": status,
			"result": result_text or "",
		}
		if code:
			payload["code"] = code
		if execution_output:
			payload["execution_output"] = execution_output
		if error:
			payload["error"] = error
		clean_payload = {
			k: self._strip_ansi(v) if isinstance(v, str) else v for k, v in payload.items()
		}
		print(json.dumps(clean_payload, ensure_ascii=False, indent=2), file=file)

	def _emit_markdown(self, result_text, code, execution_output, *, language="python", file):
		parts = []
		if result_text:
			parts.append(f"## Result\n\n{self._strip_ansi(result_text)}")
		if code:
			lang = language or "python"
			parts.append(f"## Generated Code\n\n```{lang}\n{self._strip_ansi(code)}\n```")
		if execution_output:
			parts.append(
				f"## Execution Output\n\n```\n{self._strip_ansi(execution_output)}\n```"
			)
		print("\n\n".join(parts), file=file)

	def _emit_plain(self, result_text):
		# Default behavior — existing terminal output handles everything.
		_ = result_text
		return

	@staticmethod
	def _strip_ansi(text: str) -> str:
		"""Remove ANSI escape codes from a string."""
		if not text:
			return ""
		return _ANSI_ESCAPE.sub("", text)

	@classmethod
	def from_args(cls, args, *, isatty: Optional[bool] = None) -> "OutputFormatter":
		"""Construct from parsed CLI args (``None`` format → auto-detect)."""
		tty = sys.stdout.isatty() if isatty is None else bool(isatty)
		fmt_str = getattr(args, "output_format", None)
		no_color = bool(getattr(args, "no_color", False))

		if fmt_str is None:
			# Auto-detect: JSON when piped, plain on a real TTY.
			if not tty:
				logger.debug(
					"[OutputFormatter] Non-TTY detected — auto-switching to JSON output"
				)
				return cls(fmt=OutputFormat.JSON, no_color=True, isatty=tty)
			return cls(fmt=OutputFormat.PLAIN, no_color=no_color, isatty=tty)

		return cls(fmt=OutputFormat(fmt_str), no_color=no_color or not tty, isatty=tty)
