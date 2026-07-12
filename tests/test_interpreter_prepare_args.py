# -*- coding: utf-8 -*-
"""Unit coverage for interpreter.py prepare_args / argparse helpers."""

from __future__ import annotations

import unittest
from argparse import Namespace
from unittest.mock import patch

import interpreter as interpreter_entry


class TestPrepareArgs(unittest.TestCase):
	def _base(self, **kwargs):
		# Default to CLI so prepare_args does not launch TUI / prompt stdin.
		defaults = dict(
			unsafe=False,
			sandbox="subprocess",
			safety=None,
			timeout=30,
			gemini_style=False,
			image=None,
			yes=False,
			yolo=False,
			mcp_server=None,
			mode="code",
			model="local-model",
			output_format=None,
			no_color=False,
			cli=True,
			tui=False,
			agentic=False,
			free=False,
			stream=False,
			list_free=False,
			local=False,
			ollama=None,
			attach=None,
			eda=None,
			exec=False,
			save_code=False,
			display_code=False,
			file=None,
			prompt=None,
			history=False,
			upgrade=False,
			agent=False,
			session=None,
			list_sessions=False,
			delete_session=None,
			new_session=False,
			search=False,
			search_provider=None,
			search_api_key=None,
			science=False,
			interactive_charts=False,
			plot_theme=None,
			report=False,
			no_auto_install=False,
			lang="python",
			mcp=None,
			max_context_tokens=8000,
		)
		defaults.update(kwargs)
		return Namespace(**defaults)

	def test_unsafe_alias(self):
		args = self._base(unsafe=True)
		out = interpreter_entry.prepare_args(args, ["prog", "--unsafe"])
		self.assertEqual(out.sandbox, "off")
		self.assertTrue(out.unsafe)

	def test_sandbox_bool_true_false(self):
		args = self._base(sandbox=True)
		out = interpreter_entry.prepare_args(args, ["prog"])
		self.assertEqual(out.sandbox, "subprocess")
		args = self._base(sandbox=False)
		out = interpreter_entry.prepare_args(args, ["prog"])
		self.assertEqual(out.sandbox, "off")

	def test_sandbox_on_and_docker(self):
		args = self._base(sandbox="on")
		out = interpreter_entry.prepare_args(args, ["prog"])
		self.assertEqual(out.sandbox, "subprocess")
		args = self._base(sandbox="docker")
		out = interpreter_entry.prepare_args(args, ["prog"])
		self.assertEqual(out.sandbox_backend, "docker")

	def test_sandbox_invalid_defaults(self):
		args = self._base(sandbox="weird")
		out = interpreter_entry.prepare_args(args, ["prog"])
		self.assertEqual(out.sandbox, "subprocess")

	def test_timeout_floor_and_bad(self):
		args = self._base(timeout=-5)
		out = interpreter_entry.prepare_args(args, ["prog"])
		self.assertEqual(out.timeout, 1)
		args = self._base(timeout="bad")
		out = interpreter_entry.prepare_args(args, ["prog"])
		self.assertEqual(out.timeout, 30)

	def test_gemini_style(self):
		args = self._base(gemini_style=True, model=None)
		with patch.object(
			interpreter_entry, "_get_default_model", return_value="gpt-4o"
		), patch(
			"libs.free_llms.resolve_free_model", return_value="openrouter-free"
		):
			out = interpreter_entry.prepare_args(args, ["prog", "--gemini-style"])
		self.assertTrue(out.agentic)
		self.assertTrue(out.free)
		self.assertTrue(out.cli)
		self.assertFalse(out.tui)
		self.assertTrue(out.stream)

	def test_image_forces_cli(self):
		args = self._base(image="x.png", tui=True, cli=False)
		out = interpreter_entry.prepare_args(args, ["prog", "--image", "x.png"])
		self.assertTrue(out.cli)
		self.assertFalse(out.tui)

	def test_ci_auto_yes(self):
		args = self._base(yes=False)
		with patch.dict("os.environ", {"CI": "1", "INTERPRETER_YES": ""}, clear=False):
			out = interpreter_entry.prepare_args(args, ["prog"])
		self.assertTrue(out.yes)

	def test_yolo_and_mcp_force_cli(self):
		args = self._base(yolo=True, yes=True, tui=True, cli=False)
		out = interpreter_entry.prepare_args(args, ["prog", "--yolo", "--yes"])
		self.assertTrue(out.cli)
		self.assertTrue(out.yolo)
		args = self._base(mcp_server=["npx", "server"], yes=False, tui=True, cli=False)
		out = interpreter_entry.prepare_args(args, ["prog"])
		self.assertTrue(out.cli)

	def test_codegen_modes(self):
		for mode in ("generate", "project"):
			args = self._base(mode=mode, tui=True, cli=False)
			out = interpreter_entry.prepare_args(args, ["prog"])
			self.assertTrue(out.cli)
			self.assertFalse(out.tui)

	def test_output_format_forces_cli(self):
		args = self._base(output_format="json", tui=True, cli=False)
		out = interpreter_entry.prepare_args(args, ["prog"])
		self.assertTrue(out.cli)
		self.assertFalse(out.stream)
		args = self._base(no_color=True, tui=True, cli=False)
		out = interpreter_entry.prepare_args(args, ["prog"])
		self.assertTrue(out.cli)

	def test_get_default_model(self):
		with patch.object(
			interpreter_entry.UtilityManager,
			"get_default_model_name",
			return_value="gpt-4o",
		):
			self.assertEqual(interpreter_entry._get_default_model(), "gpt-4o")

	def test_build_parser_smoke(self):
		parser = interpreter_entry.build_parser()
		ns = parser.parse_args(["--cli", "-m", "local-model"])
		self.assertTrue(ns.cli)
		self.assertEqual(ns.model, "local-model")


if __name__ == "__main__":
	unittest.main()
