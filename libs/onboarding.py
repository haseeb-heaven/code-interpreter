# -*- coding: utf-8 -*-
"""First-run identity / onboarding helpers for Code Interpreter.

Shows a one-time welcome banner so new users understand the product
positioning (free, local, plain-English tasks) without logging secrets.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Callable, Optional, Union

logger = logging.getLogger(__name__)

# Sentinel filename under the user's home directory (Issue #220).
WELCOME_SENTINEL_NAME = ".code_interpreter_welcomed"

# ASCII-only banner so Windows cp1252 / charmap consoles can print it.
FIRST_RUN_WELCOME = """
+==========================================================+
|         Code Interpreter - Free & Local                  |
|  Describe any task in plain English. Examples:           |
|                                                          |
|  > analyze data.csv and show me a summary                |
|  > resize all images in ./photos to 800px wide           |
|  > scrape top 10 HackerNews posts and save to CSV        |
|  > rename all PDFs in this folder with today's date      |
|                                                          |
|  Type /free to see zero-cost model options               |
|  Type /help for all commands                             |
+==========================================================+
"""


def welcome_sentinel_path(home_dir: Optional[Union[str, Path]] = None) -> Path:
	"""Return the absolute path of the first-run welcome sentinel file."""
	try:
		if home_dir is not None:
			base = Path(home_dir)
		else:
			# Allow tests / CI to redirect without touching the real home dir.
			override = os.environ.get("CODE_INTERPRETER_HOME") or os.environ.get(
				"INTERPRETER_HOME"
			)
			base = Path(override) if override else Path.home()
		return base / WELCOME_SENTINEL_NAME
	except Exception as exc:
		logger.error("Failed to resolve welcome sentinel path: %s", exc)
		raise


def has_seen_welcome(home_dir: Optional[Union[str, Path]] = None) -> bool:
	"""Return True when the first-run welcome has already been shown."""
	try:
		return welcome_sentinel_path(home_dir).exists()
	except Exception as exc:
		logger.warning("Could not check welcome sentinel: %s", exc)
		return True  # fail closed — do not spam welcome on errors


def mark_welcome_seen(home_dir: Optional[Union[str, Path]] = None) -> bool:
	"""Create the sentinel file. Returns True on success."""
	try:
		path = welcome_sentinel_path(home_dir)
		path.parent.mkdir(parents=True, exist_ok=True)
		path.touch(exist_ok=True)
		logger.info("First-run welcome marked seen at %s", path)
		return True
	except OSError as exc:
		logger.warning("Could not write welcome sentinel: %s", exc)
		return False
	except Exception as exc:
		logger.error("Unexpected error writing welcome sentinel: %s", exc)
		return False


def _safe_print(text: str, print_fn: Callable[..., None] = print) -> None:
	"""Print welcome text with a Windows-safe encoding fallback."""
	try:
		print_fn(text)
		return
	except UnicodeEncodeError:
		logger.debug("print_fn failed encoding; retrying with ASCII fallback")
	# Fallback: encode for the active stdout encoding, dropping unsupported glyphs.
	encoding = getattr(sys.stdout, "encoding", None) or "ascii"
	safe = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
	print_fn(safe)


def maybe_show_first_run_welcome(
	home_dir: Optional[Union[str, Path]] = None,
	*,
	force: bool = False,
	print_fn=print,
) -> bool:
	"""Print the first-run welcome once (unless ``force``).

	Returns True when the banner was printed.
	Never logs API keys or .env contents.
	"""
	try:
		if not force and has_seen_welcome(home_dir):
			logger.debug("Skipping first-run welcome (already seen)")
			return False
		_safe_print(FIRST_RUN_WELCOME, print_fn=print_fn)
		mark_welcome_seen(home_dir)
		return True
	except Exception as exc:
		logger.error("Failed to show first-run welcome: %s", exc)
		return False
