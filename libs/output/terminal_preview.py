# -*- coding: utf-8 -*-
"""Inline terminal image preview helpers (Issue #223)."""

from __future__ import annotations

import base64
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def try_inline_preview(image_path: Path, print_fn=print) -> bool:
	"""Try to display an image inline; fall back to a clear path message."""
	path = Path(image_path)
	term = os.environ.get("TERM", "")
	term_program = os.environ.get("TERM_PROGRAM", "")
	try:
		if term_program == "iTerm.app" and path.is_file():
			data = base64.b64encode(path.read_bytes()).decode("ascii")
			size = path.stat().st_size
			print_fn(
				f"\033]1337;File=inline=1;size={size};width=80%;height=auto:{data}\a"
			)
			return True
		if term == "xterm-kitty" and path.is_file():
			subprocess.run(
				["kitty", "+kitten", "icat", str(path)], check=False, capture_output=True
			)
			return True
	except Exception as exc:
		logger.debug("Inline preview failed: %s", exc)

	print_fn(f"Chart saved -> {path}")
	print_fn(f"   Open with: open {path}  (mac) | xdg-open {path}  (linux) | start {path} (win)")
	return False
