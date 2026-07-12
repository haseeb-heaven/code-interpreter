# -*- coding: utf-8 -*-
"""Unit coverage for the persisted no-args wizard config (#feature/persistent-wizard-config).

Covers:
  - WizardConfigStore round-trip (save -> load) and secret-safety (never persists keys).
  - prepare_args(): bare invocation skips the wizard and reuses a saved config.
  - prepare_args(): --config forces the wizard even when a saved config exists.
  - main(): cancelling a wizard selector (KeyboardInterrupt) exits cleanly (SystemExit),
    instead of letting the exception escape to the top level.
"""

from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import interpreter as interpreter_entry
from libs.core.wizard_config import (
	WIZARD_CONFIG_FIELDS,
	WizardConfigStore,
	apply_wizard_config_to_args,
	settings_from_namespace,
)


def _base_prepare_args(**kwargs):
	"""Minimal argparse-like Namespace, matching interpreter.build_parser() defaults."""
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
		mode=None,
		model=None,
		output_format=None,
		no_color=False,
		cli=False,
		tui=False,
		config=False,
		agentic=False,
		free=False,
		stream=True,
		list_free=False,
		local=False,
		ollama=None,
		attach=None,
		eda=None,
		exec=False,
		save_code=False,
		display_code=False,
		file=None,
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
	)
	defaults.update(kwargs)
	return Namespace(**defaults)


class TestWizardConfigStoreRoundTrip(unittest.TestCase):
	def setUp(self):
		self._tmpdir = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmpdir.cleanup)
		self.config_path = Path(self._tmpdir.name) / "config.json"

	def test_save_then_load_round_trip(self):
		store = WizardConfigStore(self.config_path)
		out = Namespace(
			mode="code", model="openrouter-free", lang="python", display_code=True,
			exec=False, save_code=False, history=True, agentic=True, agent=False,
			gemini_style=False, free=True, stream=True, search=False,
			output_format=None, safety="standard", sandbox="subprocess",
			sandbox_backend="subprocess", unsafe=False, session="my-session",
			yolo=False, yes=False, science=False, interactive_charts=False,
			image=None, attach=None, mcp_server=None,
		)

		store.save(settings_from_namespace(out))
		self.assertTrue(store.exists())

		loaded = store.load()
		self.assertIsNotNone(loaded)
		self.assertEqual(loaded["mode"], "code")
		self.assertEqual(loaded["model"], "openrouter-free")
		self.assertTrue(loaded["agentic"])
		self.assertTrue(loaded["free"])
		self.assertEqual(loaded["session"], "my-session")
		self.assertEqual(loaded["sandbox"], "subprocess")

	def test_load_missing_file_returns_none(self):
		store = WizardConfigStore(self.config_path)
		self.assertFalse(store.exists())
		self.assertIsNone(store.load())

	def test_load_corrupt_file_returns_none(self):
		self.config_path.parent.mkdir(parents=True, exist_ok=True)
		self.config_path.write_text("{not valid json", encoding="utf-8")
		store = WizardConfigStore(self.config_path)
		self.assertIsNone(store.load())

	def test_save_never_persists_unknown_or_secret_shaped_keys(self):
		"""Only WIZARD_CONFIG_FIELDS may ever be written -- never API keys."""
		store = WizardConfigStore(self.config_path)
		settings = {
			"mode": "code",
			"model": "gpt-4o",
			# Simulate an accidental secret making it into the settings dict;
			# WizardConfigStore.save() must filter it out regardless.
			"api_key": "sk-should-never-be-written",
			"search_api_key": "tvly-should-never-be-written",
			"totally_unknown_field": "ignored",
		}
		store.save(settings)

		raw_text = self.config_path.read_text(encoding="utf-8")
		self.assertNotIn("sk-should-never-be-written", raw_text)
		self.assertNotIn("tvly-should-never-be-written", raw_text)
		self.assertNotIn("api_key", raw_text)
		self.assertNotIn("totally_unknown_field", raw_text)

		loaded = store.load()
		self.assertEqual(set(loaded.keys()), {"mode", "model"})

	def test_save_empty_settings_does_not_create_file(self):
		store = WizardConfigStore(self.config_path)
		store.save({})
		self.assertFalse(store.exists())

	def test_clear_removes_file(self):
		store = WizardConfigStore(self.config_path)
		store.save({"mode": "code"})
		self.assertTrue(store.exists())
		store.clear()
		self.assertFalse(store.exists())

	def test_apply_wizard_config_to_args_only_sets_known_fields(self):
		args = _base_prepare_args()
		apply_wizard_config_to_args(args, {"mode": "chat", "model": "gpt-4o", "bogus": "x"})
		self.assertEqual(args.mode, "chat")
		self.assertEqual(args.model, "gpt-4o")
		self.assertFalse(hasattr(args, "bogus"))

	def test_all_wizard_config_fields_are_non_secret_preferences(self):
		"""Guard against future contributors adding a key-shaped field by accident."""
		forbidden_substrings = ("key", "secret", "token", "password")
		for field in WIZARD_CONFIG_FIELDS:
			lowered = field.lower()
			for bad in forbidden_substrings:
				self.assertNotIn(bad, lowered, f"{field!r} looks secret-shaped; do not persist it")


class TestPrepareArgsWizardPersistence(unittest.TestCase):
	def setUp(self):
		self._tmpdir = tempfile.TemporaryDirectory()
		self.addCleanup(self._tmpdir.cleanup)
		self.config_path = Path(self._tmpdir.name) / "config.json"
		patcher = patch("libs.core.wizard_config.CONFIG_PATH", self.config_path)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_bare_invocation_first_run_launches_wizard_and_persists(self):
		"""No saved config + no args -> wizard runs once, then answers are saved."""
		args = _base_prepare_args(cli=False, tui=False)
		wizard_out = _base_prepare_args(
			cli=False, tui=True, mode="code", model="openrouter-free", agentic=True,
			free=True,
		)
		with patch.object(
			interpreter_entry.TerminalUI, "launch", return_value=wizard_out
		) as mock_launch:
			with patch.object(interpreter_entry, "maybe_show_first_run_welcome"):
				result = interpreter_entry.prepare_args(args, ["prog"])

		mock_launch.assert_called_once()
		self.assertIs(result, wizard_out)
		store = WizardConfigStore(self.config_path)
		self.assertTrue(store.exists())
		loaded = store.load()
		self.assertEqual(loaded["model"], "openrouter-free")
		self.assertTrue(loaded["agentic"])

	def test_bare_invocation_second_run_skips_wizard_uses_saved_config(self):
		"""A previously-saved config makes a later bare invocation skip the wizard."""
		store = WizardConfigStore(self.config_path)
		store.save({
			"mode": "code", "model": "groq-llama-3.1-8b", "lang": "python",
			"display_code": True, "exec": False, "save_code": False, "history": False,
			"agentic": True, "agent": False, "gemini_style": False, "free": True,
			"stream": True, "search": False, "output_format": None, "safety": "standard",
			"sandbox": "subprocess", "sandbox_backend": "subprocess", "unsafe": False,
			"session": None, "yolo": False, "yes": False, "science": False,
			"interactive_charts": False, "image": None, "attach": None, "mcp_server": None,
		})

		args = _base_prepare_args(cli=False, tui=False)
		with patch.object(interpreter_entry.TerminalUI, "launch") as mock_launch:
			result = interpreter_entry.prepare_args(args, ["prog"])

		mock_launch.assert_not_called()
		self.assertEqual(result.model, "groq-llama-3.1-8b")
		self.assertTrue(result.agentic)
		self.assertTrue(result.cli)
		self.assertFalse(result.tui)

	def test_config_flag_forces_wizard_even_with_saved_config(self):
		"""--config always (re)runs the wizard, even when a saved config already exists."""
		store = WizardConfigStore(self.config_path)
		store.save({"mode": "code", "model": "old-saved-model"})

		args = _base_prepare_args(cli=False, tui=False, config=True)
		wizard_out = _base_prepare_args(
			cli=False, tui=True, mode="code", model="brand-new-model",
		)
		with patch.object(
			interpreter_entry.TerminalUI, "launch", return_value=wizard_out
		) as mock_launch:
			with patch.object(interpreter_entry, "maybe_show_first_run_welcome"):
				result = interpreter_entry.prepare_args(args, ["prog", "--config"])

		mock_launch.assert_called_once()
		self.assertEqual(result.model, "brand-new-model")
		# Wizard answers are re-saved, overwriting the old ones.
		self.assertEqual(store.load()["model"], "brand-new-model")

	def test_explicit_cli_flags_bypass_persisted_config_entirely(self):
		"""Existing entry points (e.g. -m/--agentic) are unaffected by a saved config."""
		store = WizardConfigStore(self.config_path)
		store.save({"mode": "chat", "model": "saved-model", "agentic": False})

		args = _base_prepare_args(cli=False, tui=False, model="explicit-model", mode="code")
		with patch.object(interpreter_entry.TerminalUI, "launch") as mock_launch:
			# argv has extra args -> not a bare invocation -> config/wizard both skipped.
			result = interpreter_entry.prepare_args(args, ["prog", "-m", "explicit-model"])

		mock_launch.assert_not_called()
		self.assertEqual(result.model, "explicit-model")
		self.assertEqual(result.mode, "code")

	def test_persisted_generate_mode_falls_back_to_wizard(self):
		"""generate/project need one-shot --task data that is never persisted."""
		store = WizardConfigStore(self.config_path)
		store.save({"mode": "generate", "model": "gpt-4o"})

		args = _base_prepare_args(cli=False, tui=False)
		wizard_out = _base_prepare_args(cli=True, tui=False, mode="generate", model="gpt-4o")
		with patch.object(
			interpreter_entry.TerminalUI, "launch", return_value=wizard_out
		) as mock_launch:
			with patch.object(interpreter_entry, "maybe_show_first_run_welcome"):
				interpreter_entry.prepare_args(args, ["prog"])

		mock_launch.assert_called_once()


class TestCancelledSelectionExitsCleanly(unittest.TestCase):
	"""TerminalUI._select_option raises KeyboardInterrupt on cancellation (Ctrl+C/Esc);
	main() must turn that into a clean SystemExit instead of an unhandled traceback."""

	def test_main_exits_cleanly_on_wizard_cancellation(self):
		argv = ["interpreter.py"]
		with patch.object(interpreter_entry, "build_parser") as mock_build_parser:
			parser = MagicMock()
			parser.parse_args.return_value = _base_prepare_args(cli=False, tui=False)
			mock_build_parser.return_value = parser
			with patch.object(
				interpreter_entry, "prepare_args", side_effect=KeyboardInterrupt("Selection cancelled by user.")
			):
				with self.assertRaises(SystemExit) as ctx:
					interpreter_entry.main(argv)

		self.assertEqual(ctx.exception.code, 0)

	def test_keyboard_interrupt_does_not_propagate_past_main(self):
		"""The raised exception reaching the caller must be SystemExit, never KeyboardInterrupt."""
		argv = ["interpreter.py"]
		with patch.object(interpreter_entry, "build_parser") as mock_build_parser:
			parser = MagicMock()
			parser.parse_args.return_value = _base_prepare_args(cli=False, tui=False)
			mock_build_parser.return_value = parser
			with patch.object(
				interpreter_entry, "prepare_args", side_effect=KeyboardInterrupt("Selection cancelled by user.")
			):
				try:
					interpreter_entry.main(argv)
				except KeyboardInterrupt:
					self.fail("KeyboardInterrupt must not escape main() unhandled")
				except SystemExit as exc:
					self.assertEqual(exc.code, 0)


if __name__ == "__main__":
	unittest.main()
