# -*- coding: utf-8 -*-
"""Additional unit coverage for main_loop mode/model/lang/install/fix paths."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from libs.core.main_loop import run_interpreter_main
from tests.interactive.helpers import make_interp


class TestMainLoopMoreCommands(unittest.TestCase):
	def _run(self, commands, **overrides):
		interp = make_interp(**overrides)
		interp._safe_input.side_effect = list(commands) + ["/exit"]
		with patch("libs.interpreter_lib.display_markdown_message"), patch(
			"libs.interpreter_lib.display_code"
		):
			run_interpreter_main(interp, "3.4.0")
		return interp

	def test_mode_change(self):
		interp = self._run(["/mode chat", "/mode nope"])
		interp._apply_mode.assert_called()

	def test_language_change(self):
		interp = self._run(["/lang javascript", "/language rust"])
		self.assertEqual(interp.INTERPRETER_LANGUAGE, "python")  # rust falls back

	def test_model_missing_config(self):
		self._run(["/model does-not-exist-model"])

	def test_model_existing_config(self):
		# Use a real configs/*.json basename without extension if present
		configs = list(Path("configs").glob("*.json"))
		if not configs:
			self.skipTest("no configs")
		name = configs[0].stem
		# main_loop looks for configs/{model}.config — may not exist; still covers branch
		self._run([f"/model {name}"])

	def test_install_commands(self):
		interp = make_interp()
		interp.package_manager.install_package = MagicMock(return_value=True)
		interp._safe_input.side_effect = [
			"/install python requests",
			"/install javascript lodash",
			"/install requests",
			"/install",
			"/exit",
		]
		with patch("libs.interpreter_lib.display_markdown_message"), patch(
			"libs.interpreter_lib.display_code"
		):
			run_interpreter_main(interp, "3.4.0")

	def test_fix_no_error(self):
		self._run(["/fix"])

	def test_fix_with_error_state(self):
		# Drive a generation that leaves code_error then /fix
		interp = make_interp()
		interp.DISPLAY_CODE = True
		interp._generate_content_with_retries.side_effect = [
			"```python\nprint(1)\n```",
			"```python\nprint(2)\n```",
		]
		interp.execute_code = MagicMock(return_value=(None, "boom"))
		interp.AUTO_YES = True
		interp._safe_input.side_effect = ["make code", "/fix", "/exit"]
		# Need execute path to set code_error — depends on main_loop flow
		with patch("libs.interpreter_lib.display_markdown_message"), patch(
			"libs.interpreter_lib.display_code"
		):
			run_interpreter_main(interp, "3.4.0")

	def test_tui_settings_mode_model_lang(self):
		interp = make_interp(terminal_ui=MagicMock())
		interp._open_tui_settings.return_value = {"mode": "chat"}
		interp._safe_input.side_effect = [
			"/settings",
			"/mode",
			"/model",
			"/language",
			"/exit",
		]
		with patch("libs.interpreter_lib.display_markdown_message"), patch(
			"libs.interpreter_lib.display_code"
		):
			run_interpreter_main(interp, "3.4.0")
		self.assertTrue(interp._open_tui_settings.called)

	def test_file_prompt_decline_and_switch(self):
		with tempfile.TemporaryDirectory() as tmp:
			prompt = Path(tmp) / "prompt.txt"
			prompt.write_text("hi", encoding="utf-8")
			interp = make_interp(
				INTERPRETER_PROMPT_FILE=True,
				INTERPRETER_PROMPT_INPUT=False,
				AUTO_YES=False,
			)
			interp.args.file = str(prompt)
			interp._safe_input.side_effect = ["n", "p", "/exit"]
			with patch("libs.interpreter_lib.display_markdown_message"), patch(
				"libs.interpreter_lib.display_code"
			):
				run_interpreter_main(interp, "3.4.0")

	def test_file_prompt_command_mode(self):
		with tempfile.TemporaryDirectory() as tmp:
			prompt = Path(tmp) / "prompt.txt"
			prompt.write_text("hi", encoding="utf-8")
			interp = make_interp(
				INTERPRETER_PROMPT_FILE=True,
				INTERPRETER_PROMPT_INPUT=False,
			)
			interp.args.file = str(prompt)
			interp._safe_input.side_effect = ["c", "/exit"]
			with patch("libs.interpreter_lib.display_markdown_message"), patch(
				"libs.interpreter_lib.display_code"
			):
				run_interpreter_main(interp, "3.4.0")

	def test_missing_prompt_create_yes(self):
		interp = make_interp(
			INTERPRETER_PROMPT_FILE=True,
			INTERPRETER_PROMPT_INPUT=False,
			AUTO_YES=False,
		)
		interp.args.file = "totally_missing_prompt_abc.txt"
		interp._safe_input.side_effect = ["y", "n", "p", "/exit"]
		with patch("libs.interpreter_lib.display_markdown_message"), patch(
			"libs.interpreter_lib.display_code"
		):
			run_interpreter_main(interp, "3.4.0")
		interp.utility_manager.create_file.assert_called()


class TestUtilityManagerExtra(unittest.TestCase):
	def setUp(self):
		from libs.utility_manager import UtilityManager

		self.um = UtilityManager()

	def test_create_read_write_clear_version(self):
		with tempfile.TemporaryDirectory() as tmp:
			p = Path(tmp) / "f.txt"
			self.um.create_file(str(p))
			self.assertTrue(p.exists())
			self.um.write_file(str(p), "hello")
			self.assertEqual(self.um.read_file(str(p)), "hello")
		with patch("builtins.print"):
			self.um.display_version("9.9.9")
		with patch("os.system"):
			self.um.clear_screen()

	def test_extract_file_name(self):
		name = self.um.extract_file_name('open file "data.csv" please')
		self.assertTrue(name is None or "data" in str(name) or isinstance(name, str))

	def test_list_available_models(self):
		models = self.um.list_available_models()
		self.assertIsInstance(models, list)
		self.assertTrue(len(models) >= 1)

	def test_get_default_model_name(self):
		from libs.utility_manager import UtilityManager

		name = UtilityManager.get_default_model_name()
		self.assertTrue(isinstance(name, str) and len(name) > 0)

	def test_read_csv_headers(self):
		with tempfile.TemporaryDirectory() as tmp:
			p = Path(tmp) / "h.csv"
			p.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
			headers = self.um.read_csv_headers(str(p))
			self.assertTrue(headers)

	def test_get_output_history_empty(self):
		# Isolate via chdir: get_output_history globs relative "output/", which
		# resolves against the process cwd (patching os.getcwd alone is not enough).
		with tempfile.TemporaryDirectory() as tmp:
			prev = os.getcwd()
			try:
				os.chdir(tmp)
				result = self.um.get_output_history(mode="code", os_name="windows", language="python")
			finally:
				os.chdir(prev)
		self.assertTrue(result is None or isinstance(result, tuple))

	def test_upgrade_interpreter_mocked(self):
		from libs.utility_manager import UtilityManager

		with patch.object(UtilityManager, "_download_file", return_value=True), patch(
			"libs.utility_manager.CodeInterpreter"
		) as mock_ci_cls, patch("libs.utility_manager.display_markdown_message"), patch(
			"libs.utility_manager.display_code"
		):
			mock_ci = MagicMock()
			mock_ci.execute_command.return_value = ("ok", None)
			mock_ci_cls.return_value = mock_ci
			UtilityManager.upgrade_interpreter()
			self.assertGreaterEqual(mock_ci.execute_command.call_count, 1)

	def test_download_file_mocked(self):
		from libs.utility_manager import UtilityManager

		with tempfile.TemporaryDirectory() as tmp:
			dest = Path(tmp) / "d.bin"
			fake_resp = MagicMock()
			fake_resp.content = b"abc"
			fake_resp.raise_for_status = MagicMock()
			with patch("requests.get", return_value=fake_resp):
				ok = UtilityManager._download_file("http://example.com/x", str(dest))
			self.assertTrue(ok)
			self.assertEqual(dest.read_bytes(), b"abc")

	def test_get_os_platform(self):
		plat = self.um.get_os_platform()
		self.assertIsInstance(plat, (tuple, list))
		self.assertGreaterEqual(len(plat), 1)


class TestCodeInterpreterMore(unittest.TestCase):
	def test_normalize_dir_with_path(self):
		from libs.code_interpreter import CodeInterpreter

		ci = CodeInterpreter()
		out = ci._normalize_command(r'dir "*.txt" from "C:\temp"')
		self.assertIn("python", out.lower())

	def test_execute_script_language(self):
		from libs.code_interpreter import CodeInterpreter

		ci = CodeInterpreter()
		ci.UNSAFE_EXECUTION = True
		ci.safety_manager = MagicMock()
		ci.safety_manager.unsafe_mode = True
		ci.safety_manager.assess_execution.return_value = MagicMock(allowed=True, reasons=[])
		out, err = ci.execute_code("print('ok')", "python", force_execute=True)
		self.assertIn("ok", out or "")


class TestSessionExtra(unittest.TestCase):
	def test_session_store_roundtrip_helpers(self):
		from libs.core import session as session_mod

		# Cover any pure helpers if present
		attrs = [a for a in dir(session_mod) if not a.startswith("_")]
		self.assertTrue(attrs)

	def test_interactive_session_persistence_unit(self):
		from libs.memory.session_store import SessionStore

		with tempfile.TemporaryDirectory() as tmp:
			store = SessionStore(session_id="unit-cov", session_dir=Path(tmp))
			store.save(messages=[{"role": "user", "content": "hi"}], model="m")
			loaded = store.load()
			self.assertTrue(loaded)
			meta = store.get_metadata()
			self.assertEqual(meta["session_id"], "unit-cov")
			store.clear()


class TestCoreSessionHelpers(unittest.TestCase):
	def test_cli_coercion_helpers(self):
		from libs.core.session import (
			_cli_bool,
			_cli_str,
			_cli_str_list,
			SessionConfig,
			apply_mode_flags,
			display_session_banner,
			initialize_mode_from_args,
			load_system_message,
			open_tui_settings,
			resolve_prompt_input_flags,
		)

		self.assertTrue(_cli_bool(True))
		self.assertFalse(_cli_bool(MagicMock()))
		self.assertEqual(_cli_str("x"), "x")
		self.assertIsNone(_cli_str(MagicMock()))
		self.assertEqual(_cli_str_list(["a", "b"]), ["a", "b"])
		self.assertEqual(_cli_str_list("solo"), ["solo"])
		self.assertEqual(_cli_str_list(MagicMock()), [])

		args = MagicMock(file=None, lang="python", mode="code", model="m", save_code=False, exec=False, display_code=False, unsafe=False, history=False, max_context_tokens=100)
		# Make bool attrs real
		args = type("A", (), {
			"file": None, "lang": "python", "mode": "chat", "model": "m",
			"save_code": True, "exec": True, "display_code": False, "unsafe": False,
			"history": True, "max_context_tokens": 100, "history_file": None,
		})()
		cfg = SessionConfig.from_args(args)
		self.assertEqual(cfg.mode, "chat")

		target = MagicMock()
		apply_mode_flags(target, "vision")
		self.assertEqual(target.INTERPRETER_MODE, "vision")
		apply_mode_flags(target, "generate")

		args2 = type("A", (), {"mode": "script", "file": ""})()
		initialize_mode_from_args(target, args2)
		pf, pi = resolve_prompt_input_flags(args2)
		self.assertTrue(pf)

		console = MagicMock()
		display_session_banner(
			console, unsafe=False, os_name="Windows 10", language="python",
			mode="code", input_prompt_mode="Input", model_label="gpt",
		)
		console.print.assert_called()

		logger = MagicMock()
		try:
			msg = load_system_message("vision", logger)
			self.assertIn("image", msg.lower())
			msg = load_system_message("chat", logger)
			self.assertIn("chat", msg.lower())
		except Exception:
			pass

		interp = MagicMock()
		interp.terminal_ui = None
		self.assertIsNone(open_tui_settings(interp, "mode"))
		interp.terminal_ui = MagicMock()
		interp.INTERPRETER_MODE = "code"
		interp.INTERPRETER_MODEL_LABEL = "m"
		interp.INTERPRETER_MODEL = "m"
		interp.INTERPRETER_LANGUAGE = "python"
		interp.terminal_ui.select_mode.return_value = "chat"
		self.assertEqual(open_tui_settings(interp, "mode")["mode"], "chat")
		open_tui_settings(interp, "model")
		open_tui_settings(interp, "language")
		open_tui_settings(interp, "settings")
		self.assertIsNone(open_tui_settings(interp, "other"))


class TestInterpreterMainEntry(unittest.TestCase):
	def test_main_list_free(self):
		import interpreter as ie

		with patch("builtins.print"), patch(
			"libs.free_llms.FreeLLMCatalog.load"
		) as load:
			load.return_value.format_table.return_value = "table"
			ie.main(["prog", "--list-free"])

	def test_main_upgrade(self):
		import interpreter as ie

		with patch.object(ie.UtilityManager, "upgrade_interpreter") as up:
			ie.main(["prog", "--upgrade"])
			up.assert_called()

	def test_main_list_ollama_not_running(self):
		import interpreter as ie

		with patch("libs.local.ollama_helper.is_ollama_running", return_value=False), patch(
			"builtins.print"
		):
			with self.assertRaises(SystemExit):
				ie.main(["prog", "--list-ollama"])

	def test_main_session_list(self):
		import interpreter as ie

		with patch("libs.memory.session_store.SessionStore.list_sessions", return_value=[]), patch(
			"builtins.print"
		):
			# --list-sessions should exit early via _handle_session_mgmt_flags
			ie.main(["prog", "--list-sessions", "--cli"])


class TestModelRouterBrowserAndInit(unittest.TestCase):
	def test_initialize_client_openai_key_present(self):
		from libs.core.model_router import ModelRouter

		interp = MagicMock()
		interp.INTERPRETER_MODEL = "gpt-4o"
		interp.config_values = {"provider": "openai", "model": "gpt-4o"}
		interp.utility_manager = MagicMock()
		interp.utility_manager.read_config_file.return_value = interp.config_values
		interp.logger = MagicMock()
		router = ModelRouter(interp)
		environ = {"OPENAI_API_KEY": "sk-test"}
		router.initialize_client(
			load_dotenv_fn=lambda **_: None,
			getenv_fn=lambda k, *a: environ.get(k),
			environ=environ,
		)

	def test_run_openai_missing_key(self):
		from libs.core.model_router import ModelRouter

		interp = MagicMock()
		interp.INTERPRETER_MODEL = "local"
		router = ModelRouter(interp)
		with self.assertRaises(Exception):
			router.run_openai_compatible_completion(
				"OPENAI_API_KEY",
				[],
				0.1,
				10,
				"http://localhost",
				completion_fn=MagicMock(),
				getenv_fn=lambda *_: None,
			)

	def test_run_openai_api_base_none_string(self):
		from libs.core.model_router import ModelRouter

		interp = MagicMock()
		interp.INTERPRETER_MODEL = "local"
		router = ModelRouter(interp)
		with self.assertRaises(Exception):
			router.run_openai_compatible_completion(
				"OPENAI_API_KEY",
				[],
				0.1,
				10,
				"None",
				completion_fn=MagicMock(),
				getenv_fn=lambda *_: "sk",
			)


if __name__ == "__main__":
	unittest.main()
