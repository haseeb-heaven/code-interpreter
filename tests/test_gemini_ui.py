# -*- coding: utf-8 -*-
"""Unit tests for the Gemini-CLI-inspired startup banner/tips/footer (libs.agent.gemini_ui).

Tests assert on *structure* (row counts/widths, substrings, tuple shapes) and
that rendering never raises for a range of terminal widths and console
encodings — not on exact ANSI byte output, which is brittle and unnecessary.
"""

from __future__ import annotations

import io
import unittest

from libs.agent.gemini_ui import (
	BANNER_LINES,
	TIPS_HEADER,
	context_metadata_line,
	footer_parts,
	gradient_color_at,
	render_banner,
	render_context_line,
	render_footer,
	render_persistent_banner,
	render_startup_screen,
	render_status_bar,
	render_tips,
	render_wordmark_text,
	scale_rows,
	shorten_cwd,
	supports_unicode,
	tips_lines,
	word_bitmap_rows,
)


class TestBitmapFont(unittest.TestCase):
	def test_word_bitmap_has_expected_row_count(self):
		rows = word_bitmap_rows("INTER")
		self.assertEqual(len(rows), 6)
		# All rows must be the same width for a rectangular glyph grid.
		widths = {len(r) for r in rows}
		self.assertEqual(len(widths), 1)

	def test_banner_lines_concatenate_to_interpreter(self):
		self.assertEqual("".join(BANNER_LINES), "INTERPRETER")

	def test_unknown_letters_render_as_blank_cell_not_crash(self):
		rows = word_bitmap_rows("ZQ!")
		self.assertEqual(len(rows), 6)
		self.assertTrue(all(set(r) <= {"."} for r in rows))

	def test_empty_word_returns_blank_rows(self):
		rows = word_bitmap_rows("")
		self.assertEqual(len(rows), 6)

	def test_prefix_glyph_is_prepended(self):
		plain = word_bitmap_rows("I")
		with_prefix = word_bitmap_rows("I", prefix=("#....", ".#...", "..#..", "..#..", ".#...", "#...."))
		for p, wp in zip(plain, with_prefix):
			self.assertTrue(wp.endswith(p))
			self.assertGreater(len(wp), len(p))

	def test_scale_rows_widens_each_column(self):
		rows = [".#."]
		scaled = scale_rows(rows, pixel_width=3)
		self.assertEqual(scaled[0], "...###...")

	def test_scale_rows_noop_for_pixel_width_one(self):
		rows = ["#.#"]
		self.assertEqual(scale_rows(rows, pixel_width=1), rows)


class TestGradient(unittest.TestCase):
	def test_gradient_endpoints_match_stops(self):
		self.assertEqual(gradient_color_at(0.0), (59, 130, 246))
		self.assertEqual(gradient_color_at(1.0), (236, 72, 153))

	def test_gradient_midpoint_is_purple_stop(self):
		self.assertEqual(gradient_color_at(0.5), (168, 85, 247))

	def test_gradient_clamps_out_of_range_inputs(self):
		self.assertEqual(gradient_color_at(-5.0), gradient_color_at(0.0))
		self.assertEqual(gradient_color_at(5.0), gradient_color_at(1.0))

	def test_gradient_returns_rgb_triplet_in_byte_range(self):
		for t in (0.0, 0.25, 0.5, 0.75, 1.0):
			rgb = gradient_color_at(t)
			self.assertEqual(len(rgb), 3)
			self.assertTrue(all(0 <= c <= 255 for c in rgb))


class TestUnicodeSupportDetection(unittest.TestCase):
	def test_legacy_windows_console_is_unsupported(self):
		console = type("C", (), {"legacy_windows": True})()
		self.assertFalse(supports_unicode(console))

	def test_cp1252_stream_is_unsupported(self):
		class Stream:
			encoding = "cp1252"

		console = type("C", (), {"legacy_windows": False, "file": Stream()})()
		self.assertFalse(supports_unicode(console))

	def test_utf8_stream_is_supported(self):
		class Stream:
			encoding = "utf-8"

		console = type("C", (), {"legacy_windows": False, "file": Stream()})()
		self.assertTrue(supports_unicode(console))

	def test_missing_attrs_default_to_supported(self):
		console = object()
		self.assertTrue(supports_unicode(console))


class _FakeStream:
	"""Minimal writable stream with a settable ``encoding`` (io.StringIO's is read-only)."""

	def __init__(self, encoding: str = "utf-8"):
		self.encoding = encoding
		self._buf = io.StringIO()

	def write(self, text):
		return self._buf.write(text)

	def flush(self):
		return None

	def isatty(self):
		return True

	def getvalue(self):
		return self._buf.getvalue()


class TestBannerRendering(unittest.TestCase):
	def _console(self, width=100, encoding="utf-8", legacy_windows=False):
		from rich.console import Console

		buf = _FakeStream(encoding)
		return Console(file=buf, width=width, force_terminal=True, legacy_windows=legacy_windows), buf

	def test_render_banner_does_not_crash_at_standard_widths(self):
		for width in (40, 60, 80, 100, 120):
			console, buf = self._console(width=width)
			render_banner(console, width=width)
			self.assertTrue(buf.getvalue())  # something was printed

	def test_render_banner_narrow_width_falls_back_to_plain_text(self):
		console, buf = self._console(width=20)
		render_banner(console, width=20)
		self.assertIn("INTERPRETER", buf.getvalue())

	def test_render_banner_legacy_windows_never_emits_raw_block_glyph(self):
		console, buf = self._console(legacy_windows=True)
		render_banner(console)
		self.assertNotIn("\u2588", buf.getvalue())
		self.assertIn("INTERPRETER", buf.getvalue())

	def test_render_wordmark_text_width_matches_scaling(self):
		text = render_wordmark_text("I", pixel_width=2)
		lines = text.plain.split("\n")
		self.assertEqual(len(lines), 6)
		self.assertTrue(all(len(line) == 10 for line in lines))

	def test_render_banner_default_console_smoke(self):
		# No console passed — must use the internal default without raising.
		render_banner()


class TestPersistentBanner(unittest.TestCase):
	"""``render_persistent_banner`` is the shared banner-only entry point used by
	every interactive REPL (--cli/--agentic/--gemini-style) and by
	``UtilityManager.clear_screen`` to keep the banner "pinned" after a clear."""

	def _console(self, width=100):
		from rich.console import Console

		buf = _FakeStream("utf-8")
		return Console(file=buf, width=width, force_terminal=True), buf

	def test_render_persistent_banner_prints_same_content_as_render_banner(self):
		console_a, buf_a = self._console()
		console_b, buf_b = self._console()
		render_persistent_banner(console_a)
		render_banner(console_b)
		self.assertEqual(buf_a.getvalue(), buf_b.getvalue())

	def test_render_persistent_banner_does_not_crash_default_console(self):
		render_persistent_banner()

	def test_render_persistent_banner_omits_tips_and_footer(self):
		console, buf = self._console()
		render_persistent_banner(console)
		out = buf.getvalue()
		self.assertNotIn(TIPS_HEADER, out)


class TestTips(unittest.TestCase):
	def test_tips_lines_reference_real_commands(self):
		joined = " ".join(tips_lines())
		for cmd in ("/free", "/model", "/settings", "/help"):
			self.assertIn(cmd, joined)

	def test_tips_lines_are_ascii_safe(self):
		for line in tips_lines():
			line.encode("ascii")  # raises if any non-ASCII character sneaks in

	def test_render_tips_does_not_crash(self):
		from rich.console import Console

		console = Console(file=io.StringIO(), force_terminal=True)
		render_tips(console)


class TestFooter(unittest.TestCase):
	def test_shorten_cwd_collapses_home_prefix(self):
		result = shorten_cwd("/home/user/projects/foo", home="/home/user")
		self.assertTrue(result.startswith("~"))
		self.assertIn("foo", result)

	def test_shorten_cwd_leaves_non_home_paths_untouched(self):
		result = shorten_cwd("/opt/other", home="/home/user")
		self.assertEqual(result, "/opt/other")

	def test_footer_parts_sandboxed_vs_unsafe(self):
		_, center_safe, _ = footer_parts("/x", True, False)
		_, center_unsafe, _ = footer_parts("/x", False, False)
		self.assertIn("sandbox", center_safe.lower())
		self.assertIn("no sandbox", center_unsafe.lower())

	def test_footer_parts_auto_vs_manual(self):
		_, _, right_auto = footer_parts("/x", True, True)
		_, _, right_manual = footer_parts("/x", True, False)
		self.assertNotEqual(right_auto, right_manual)

	def test_footer_parts_are_ascii_safe(self):
		for part in footer_parts("/x", False, True):
			part.encode("ascii")

	def test_render_footer_does_not_crash(self):
		from rich.console import Console

		console = Console(file=io.StringIO(), force_terminal=True, width=100)
		render_footer(console, cwd="/x", sandboxed=True, auto_yes=False)


class TestContextMetadataLine(unittest.TestCase):
	def test_returns_none_when_nothing_real_to_report(self):
		self.assertIsNone(context_metadata_line())
		self.assertIsNone(context_metadata_line(actions_count=0, session_turns=0))

	def test_includes_actions_count_when_present(self):
		line = context_metadata_line(actions_count=4)
		self.assertIn("4", line)
		self.assertIn("Using:", line)

	def test_includes_session_turns_when_present(self):
		line = context_metadata_line(session_turns=1)
		self.assertIn("1 turn", line)

	def test_combines_both_signals(self):
		line = context_metadata_line(actions_count=4, session_turns=5)
		self.assertIn("4", line)
		self.assertIn("5 turns", line)

	def test_render_context_line_noop_when_nothing_to_show(self):
		from rich.console import Console

		buf = io.StringIO()
		console = Console(file=buf, force_terminal=True)
		render_context_line(console)
		self.assertEqual(buf.getvalue(), "")


class TestCompositeEntryPoints(unittest.TestCase):
	def test_render_startup_screen_smoke(self):
		from rich.console import Console

		console = Console(file=io.StringIO(), force_terminal=True, width=100)
		render_startup_screen(console)

	def test_render_status_bar_smoke(self):
		from rich.console import Console

		console = Console(file=io.StringIO(), force_terminal=True, width=100)
		render_status_bar(console, cwd="/x", sandboxed=False, auto_yes=True, actions_count=4, session_turns=2)


if __name__ == "__main__":
	unittest.main()
