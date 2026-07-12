# -*- coding: utf-8 -*-
"""Unit tests for libs.output.terminal_preview."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from libs.output.terminal_preview import try_inline_preview


class TestTerminalPreview(unittest.TestCase):
	def test_fallback_message_when_no_term(self):
		msgs = []
		with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
			path = Path(fh.name)
			fh.write(b"\x89PNG\r\n\x1a\n")
		try:
			with patch.dict("os.environ", {"TERM": "", "TERM_PROGRAM": ""}, clear=False):
				ok = try_inline_preview(path, print_fn=msgs.append)
			self.assertFalse(ok)
			self.assertTrue(any("Chart saved" in m for m in msgs))
		finally:
			path.unlink(missing_ok=True)

	def test_iterm_inline(self):
		msgs = []
		with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
			path = Path(fh.name)
			fh.write(b"pngdata")
		try:
			with patch.dict("os.environ", {"TERM_PROGRAM": "iTerm.app", "TERM": "xterm"}, clear=False):
				ok = try_inline_preview(path, print_fn=msgs.append)
			self.assertTrue(ok)
			self.assertTrue(any("1337;File=inline=1" in m for m in msgs))
		finally:
			path.unlink(missing_ok=True)

	def test_kitty_inline(self):
		with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
			path = Path(fh.name)
			fh.write(b"pngdata")
		try:
			with patch.dict("os.environ", {"TERM": "xterm-kitty", "TERM_PROGRAM": ""}, clear=False):
				with patch("libs.output.terminal_preview.subprocess.run") as run:
					ok = try_inline_preview(path, print_fn=lambda *_: None)
			self.assertTrue(ok)
			run.assert_called()
		finally:
			path.unlink(missing_ok=True)

	def test_exception_falls_back(self):
		msgs = []
		missing = Path("/nonexistent/chart_does_not_exist.png")
		with patch.dict("os.environ", {"TERM_PROGRAM": "iTerm.app"}, clear=False):
			ok = try_inline_preview(missing, print_fn=msgs.append)
		self.assertFalse(ok)
		self.assertTrue(any("Chart saved" in m for m in msgs))


if __name__ == "__main__":
	unittest.main()
