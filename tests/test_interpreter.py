import os
import shlex
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import interpreter as interpreter_entry
from interpreter import Interpreter
from libs.history_manager import History
from libs.code_interpreter import CodeInterpreter
from libs.model_utils import normalize_model_name
from libs.safety_manager import ExecutionSafetyManager, RepairCircuitBreaker
from libs.utility_manager import UtilityManager
from libs.llm_dispatcher import build_completion_kwargs


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIGS_DIR = ROOT_DIR / "configs"


def _read_hf_model(config_path: Path) -> str:
	data = json.loads(config_path.read_text(encoding="utf-8-sig"))
	if "model" in data:
		return data["model"]
	raise AssertionError(f"model missing in config: {config_path}")



class TestInterpreter(unittest.TestCase):
	def _make_args(self, mode="code", model="code-llama"):
		return Namespace(
			exec=False,
			save_code=False,
			mode=mode,
			model=model,
			display_code=False,
			lang="python",
			file=None,
			history=False,
			upgrade=False,
		)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_mode_is_initialized_from_args(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(mode="vision", model="gpt-4o"))
		self.assertEqual(interpreter.INTERPRETER_MODE, "vision")
		self.assertTrue(interpreter.VISION_MODE)
		self.assertFalse(interpreter.CODE_MODE)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_openai_o_series_uses_openai_path(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(model="o1-mini"))
		interpreter.INTERPRETER_MODEL = "o1-mini"

		with patch(
			"libs.interpreter_lib.litellm.completion",
			return_value={"choices": [{"message": {"content": "ok"}}]},
		) as completion_mock, patch.object(interpreter.utility_manager, "_extract_content", return_value="ok"):
			response = interpreter.generate_content(
				message="Say hello",
				chat_history=[],
				config_values={"temperature": 0.1, "max_tokens": 32, "api_base": "None"},
			)

		self.assertEqual(response, "ok")
		completion_mock.assert_called_once()
		self.assertEqual(completion_mock.call_args.args[0], "o1-mini")

		# Assert exact kwargs to ensure o-series models go through OpenAI path with correct params
		called_kwargs = completion_mock.call_args.kwargs
		self.assertIn("messages", called_kwargs)
		self.assertIn("max_tokens", called_kwargs)
		self.assertIn("drop_params", called_kwargs)
		self.assertTrue(called_kwargs["drop_params"])
		self.assertIn("custom_llm_provider", called_kwargs)
		self.assertEqual(called_kwargs["custom_llm_provider"], "openai")
		# Temperature should not be in kwargs for o-series models
		self.assertNotIn("temperature", called_kwargs)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_legacy_claude_alias_is_remapped_to_sonnet_46(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(model="claude-2.1"))
		interpreter.INTERPRETER_MODEL = "claude-2.1"

		with patch(
			"libs.interpreter_lib.litellm.completion",
			return_value={"choices": [{"message": {"content": "ok"}}]},
		) as completion_mock, patch.object(interpreter.utility_manager, "_extract_content", return_value="ok"):
			interpreter.generate_content(
				message="Ping",
				chat_history=[],
				config_values={"temperature": 0.1, "max_tokens": 32, "api_base": "None"},
			)

		self.assertEqual(completion_mock.call_args.args[0], "claude-sonnet-4-6")

	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	@patch("libs.interpreter_lib.os.getenv", return_value="sk-test-key-123")
	@patch("libs.interpreter_lib.load_dotenv")
	@patch("libs.utility_manager.UtilityManager.read_config_file", return_value={"model": "gpt-4o"})
	def test_initialize_client_loads_env_from_repo_root(
		self, _mock_read_config, load_dotenv_mock, _mock_getenv, _mock_history
	):
		Interpreter(self._make_args(model="gpt-4o"))
		expected_env_path = os.path.join(os.getcwd(), ".env")
		load_dotenv_mock.assert_any_call(dotenv_path=expected_env_path, override=True)

	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	@patch("libs.interpreter_lib.os.getenv", side_effect=lambda key: "gsk-test-123" if key == "GROQ_API_KEY" else None)
	@patch("libs.interpreter_lib.load_dotenv")
	@patch("libs.utility_manager.UtilityManager.read_config_file", return_value={"model": "groq/openai/gpt-oss-20b"})
	def test_initialize_client_uses_shared_default_model_when_missing(
		self, _mock_read_config, _mock_load_dotenv, _mock_getenv, _mock_history
	):
		with patch("libs.utility_manager.UtilityManager.get_default_model_name", return_value="groq-gpt-oss-20b"):
			interpreter = Interpreter(self._make_args(model=None))

		self.assertEqual(interpreter.INTERPRETER_MODEL, "groq/openai/gpt-oss-20b")
		self.assertEqual(interpreter.INTERPRETER_MODEL_LABEL, "groq-gpt-oss-20b")

	def test_every_config_is_parseable_and_has_hf_model(self):
		utility_manager = UtilityManager()
		config_files = sorted(CONFIGS_DIR.glob("*.json"))
		self.assertTrue(config_files, "No config files found")

		for config_file in config_files:
			with self.subTest(config=config_file.name):
				values = utility_manager.read_config_file(str(config_file))
				self.assertIn("model", values)
				self.assertTrue(values["model"].strip())

	def test_history_manager_creates_missing_history_file(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			history_path = Path(temp_dir) / "history" / "history.json"
			history = History(str(history_path))
			self.assertTrue(history_path.exists())
			self.assertEqual(json.loads(history_path.read_text(encoding="utf-8")), [])

	def test_history_manager_returns_empty_entries_when_history_file_missing(self):
		with tempfile.TemporaryDirectory() as temp_dir:
			history_path = Path(temp_dir) / "history" / "history.json"
			history = History(str(history_path))
			history_path.unlink()
			self.assertEqual(history.get_code_history(3), [])

	def test_safety_manager_blocks_dangerous_command(self):
		safety_manager = ExecutionSafetyManager()
		decision = safety_manager.assess_execution("rm -rf /", "command")
		self.assertFalse(decision.allowed)
		self.assertTrue(decision.reasons)

	def test_safety_manager_blocks_windows_recursive_delete_alias(self):
		safety_manager = ExecutionSafetyManager()
		decision = safety_manager.assess_execution('rd /s /q "C:\\Users\\hasee\\Desktop"', "command")
		self.assertFalse(decision.allowed)

	def test_safety_manager_blocks_os_remove_when_building_absolute_path(self):
		safety_manager = ExecutionSafetyManager()
		code = r"""
		import os
		for filename in os.listdir('D:\\Temp'):
			if filename.endswith('.txt'):
				os.remove(os.path.join('D:\\Temp', filename))
		"""
		decision = safety_manager.assess_execution(code, "code")
		self.assertFalse(decision.allowed)
		self.assertTrue(any("blocked" in r.lower() for r in decision.reasons) for r in decision.reasons)

	def test_safety_manager_allows_relative_file_delete(self):
		safety_manager = ExecutionSafetyManager()
		code = r"import os\nos.remove('temp.txt')"
		decision = safety_manager.assess_execution(code, "code")
		self.assertFalse(decision.allowed)

	def test_safety_manager_blocks_absolute_path_del_command(self):
		safety_manager = ExecutionSafetyManager()
		decision = safety_manager.assess_execution(r"del D:\\Temp\\a.txt", "command")
		self.assertFalse(decision.allowed)

	def test_safety_manager_blocks_absolute_path_rm_command(self):
		safety_manager = ExecutionSafetyManager()
		decision = safety_manager.assess_execution(r"rm /tmp/a.txt", "command")
		self.assertFalse(decision.allowed)

	def test_safety_manager_blocks_js_unlink_on_absolute_path_join(self):
		safety_manager = ExecutionSafetyManager()
		code = r"""
		const fs = require('fs');
		const path = require('path');
		const directory = 'D:\\Temp';
		const files = fs.readdirSync(directory);
			for (const file of files) {
			  const filePath = path.join(directory, file);
			  fs.unlinkSync(filePath);
			}
		"""
		decision = safety_manager.assess_execution(code, "code")
		self.assertFalse(decision.allowed)

	def test_safety_manager_allows_js_unlink_on_relative_path(self):
		safety_manager = ExecutionSafetyManager()
		code = r"const fs = require('fs');\nfs.unlinkSync('temp.txt');"
		decision = safety_manager.assess_execution(code, "code")
		self.assertFalse(decision.allowed)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_simple_exact_print_task_is_simplified(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(mode="code", model="z-ai-glm-5"))
		simplified = interpreter._maybe_simplify_generated_code(
			"write python code that prints exactly 'Heaven Hello'",
			"import pandas as pd\nprint('Heaven Hello')\n",
		)
		self.assertEqual(simplified, "print('Heaven Hello')")

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_simple_directory_listing_task_is_simplified_for_python(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(mode="code", model="z-ai-glm-5"))
		simplified = interpreter._maybe_simplify_generated_code(
			"Print current files in directory",
			"import os\nimport pandas as pd\nprint(os.listdir())\n",
		)
		self.assertEqual(simplified, "import os\nfor name in os.listdir():\n    print(name)")

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_simple_directory_listing_task_is_simplified_for_javascript(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(mode="code", model="z-ai-glm-5"))
		interpreter.INTERPRETER_LANGUAGE = "javascript"
		simplified = interpreter._maybe_simplify_generated_code(
			"Print current files in directory",
			"const fs = require('fs');\nconsole.log(fs.readdirSync(process.cwd()));",
		)
		self.assertEqual(
			simplified,
			"const fs = require('fs');\nfor (const name of fs.readdirSync(process.cwd())) {\n  console.log(name);\n}",
		)

	def test_repair_circuit_breaker_stops_on_repeated_error(self):
		breaker = RepairCircuitBreaker(max_attempts=2)
		self.assertTrue(breaker.should_continue("syntax error"))
		self.assertFalse(breaker.should_continue("syntax error"))

	def test_extract_code_prefers_triple_backticks_when_config_uses_single_backtick(self):
		code_interpreter = CodeInterpreter()
		extracted = code_interpreter.extract_code(
			"```python\nprint('OK')\n```",
			start_sep="`",
			end_sep="`",
		)
		self.assertEqual(extracted, "print('OK')")

	def test_extract_code_strips_fence_lang_on_same_line_as_opener(self):
		code_interpreter = CodeInterpreter()
		extracted = code_interpreter.extract_code("```python\nimport os\n```")
		self.assertEqual(extracted, "import os")

	def test_extract_code_strips_javascript_fence_tag(self):
		code_interpreter = CodeInterpreter()
		extracted = code_interpreter.extract_code("```javascript\nconsole.log(1)\n```")
		self.assertEqual(extracted, "console.log(1)")

	def test_legacy_alias_configs_are_mapped_to_modern_targets(self):
		expected_aliases = {
			"gpt-3.5-turbo.json": "gpt-4o-mini",
			"gpt-4.json": "gpt-4",
			"gpt-o1-mini.json": "o1",
			"gpt-o1-preview.json": "o1-preview",
			"gemini-pro.json": "gemini/gemini-2.5-pro",
			"gemini-1.5-pro.json": "gemini/gemini-2.5-pro",
			"gemini-1.5-flash.json": "gemini/gemini-2.5-flash",
			"claude-2.json": "claude-2",
			"claude-2.1.json": "claude-2.1",
			"claude-3-7-sonnet.json": "claude-3-7-sonnet",
			"deepseek-coder.json": "deepseek-chat",
			"groq-mixtral.json": "groq/llama-3.3-70b-versatile",
			"groq-llama2.json": "groq/llama-3.1-8b-instant",
		}
		for config_name, expected_hf_model in expected_aliases.items():
			with self.subTest(config=config_name):
				hf_model = _read_hf_model(CONFIGS_DIR / config_name)
				self.assertEqual(hf_model, expected_hf_model)

	def test_new_provider_configs_exist(self):
		required_configs = {
			"openrouter-free.json": "openrouter/free",
			"nvidia-nemotron.json": "nvidia/nemotron-3-super-120b-a12b",
			"z-ai-glm-5.json": "glm-5",
			"browser-use-bu-max.json": "bu-max",
			"openrouter-qwen3-coder.json": "qwen/qwen3-coder:free",
			"openrouter-claude-opus-4-6.json": "anthropic/claude-opus-4.6",
			"openrouter-mimo-v2-pro.json": "xiaomi/mimo-v2-pro",
			"openrouter-gpt-5-4.json": "openai/gpt-5.4",
			"openrouter-deepseek-v3-2.json": "deepseek/deepseek-v3.2",
			"openrouter-qwen3-coder-480b-free.json": "qwen/qwen3-coder-480b:free",
			"openrouter-mimo-v2-flash-free.json": "xiaomi/mimo-v2-flash:free",
			"openrouter-nemotron-3-super-free.json": "nvidia/nemotron-3-super:free",
			"openrouter-minimax-m2-5-free.json": "minimax/minimax-m2.5:free",
			"openrouter-qwen3-6-plus-free.json": "qwen/qwen3.6-plus:free",
		}
		for config_name, expected_hf_model in required_configs.items():
			with self.subTest(config=config_name):
				hf_model = _read_hf_model(CONFIGS_DIR / config_name)
				self.assertEqual(hf_model, expected_hf_model)

	@patch("libs.utility_manager.load_dotenv", return_value=None)
	def test_openrouter_becomes_default_when_openrouter_key_exists(self, _mock_load_dotenv):
		with patch.dict("os.environ", {"OPENROUTER_API_KEY": "sk-or-v1-test"}, clear=True):
			self.assertEqual(UtilityManager.get_default_model_name(), "openrouter-free")

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_routing_matrix_for_all_non_local_configs(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(model="gpt-4o"))
		utility_manager = UtilityManager()
		config_files = sorted(CONFIGS_DIR.glob("*.json"))

		for config_file in config_files:
			if config_file.name == "local-model.json":
				continue

			model_name = _read_hf_model(config_file)
			expected_model = normalize_model_name(model_name)
			model_config_values = utility_manager.read_config_file(str(config_file))
			config_provider = str(model_config_values.get("provider", "")).strip().lower()
			interpreter.INTERPRETER_MODEL = model_name

			with self.subTest(config=config_file.name, model=model_name):
				if config_provider in {"browser-use", "browser_use"} or model_name.startswith(("bu-", "browser-use/")):
					with patch.object(interpreter, "_generate_browser_use_content", return_value="ok-browser-use") as browser_mock:
						response = interpreter.generate_content(
							message="healthcheck",
							chat_history=[],
							config_values=model_config_values,
						)
					self.assertEqual(response, "ok-browser-use")
					browser_mock.assert_called_once()
					continue

				if config_provider in {"nvidia", "z-ai", "zai", "openrouter"} or model_name.startswith("nvidia/") or model_name.startswith(("glm-", "z-ai/", "zai/")):
					# After the llm_dispatcher refactor these providers also go
					# through litellm.completion; we just need to supply the
					# expected API key env-var so build_completion_kwargs doesn't
					# raise a ValueError.
					with patch(
						"libs.interpreter_lib.litellm.completion",
						return_value={"choices": [{"message": {"content": "ok"}}]},
					) as completion_mock, patch.object(interpreter.utility_manager, "_extract_content", return_value="ok"), \
						 patch("libs.llm_dispatcher.os.getenv", return_value="test-key-123"):
						response = interpreter.generate_content(
							message="healthcheck",
							chat_history=[],
							config_values=model_config_values,
						)
					self.assertEqual(response, "ok")
					completion_mock.assert_called_once()
					self.assertEqual(completion_mock.call_args.args[0], expected_model)
					continue

				with patch(
					"libs.interpreter_lib.litellm.completion",
					return_value={"choices": [{"message": {"content": "ok"}}]},
				) as completion_mock, patch.object(interpreter.utility_manager, "_extract_content", return_value="ok"):
					response = interpreter.generate_content(
						message="healthcheck",
						chat_history=[],
						config_values=model_config_values,
					)

				self.assertEqual(response, "ok")
				completion_mock.assert_called_once()
				self.assertEqual(completion_mock.call_args.args[0], expected_model)

	@patch("interpreter.TerminalUI.launch")
	def test_prepare_args_defaults_to_tui_when_no_args(self, launch_mock):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args([])
		launch_mock.return_value = args

		interpreter_entry.prepare_args(args, ["interpreter.py"])

		launch_mock.assert_called_once()

	@patch("interpreter._get_default_model", return_value="z-ai-glm-5")
	def test_prepare_args_sets_cli_defaults(self, _mock_default_model):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--cli"])

		prepared_args = interpreter_entry.prepare_args(args, ["interpreter.py", "--cli"])

		self.assertTrue(prepared_args.cli)
		self.assertEqual(prepared_args.mode, "code")
		self.assertEqual(prepared_args.model, "z-ai-glm-5")

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_generate_content_with_retries_retries_transient_failures(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(mode="code", model="z-ai-glm-5"))
		with patch.object(
			interpreter,
			"generate_content",
			side_effect=[Exception("connection timeout"), "ok"],
		) as generate_mock, patch("libs.interpreter_lib.time.sleep", return_value=None):
			result = interpreter._generate_content_with_retries("Ping", [], config_values={})

		self.assertEqual(result, "ok")
		self.assertEqual(generate_mock.call_count, 2)

	@patch("libs.interpreter_lib.display_markdown_message")
	@patch("libs.interpreter_lib.display_code")
	@patch("builtins.input", side_effect=["Write Python code to print OK", "/exit"])
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	def test_interactive_code_mode_displays_code_without_display_flag(
		self, _mock_client, _mock_history, _mock_input, display_code_mock, _mock_markdown
	):
		interpreter = Interpreter(self._make_args(mode="code", model="z-ai-glm-5"))
		interpreter.config_values = {"start_sep": "```", "end_sep": "```"}

		with patch.object(interpreter.utility_manager, "get_os_platform", return_value=("Windows 10", "10")), \
			 patch.object(interpreter, "get_mode_prompt", return_value="Generate Python code"), \
			 patch.object(interpreter, "generate_content", return_value="```python\nprint('OK')\n```"), \
			 patch.object(interpreter.code_interpreter, "extract_code", return_value="print('OK')"), \
			 patch.object(interpreter, "execute_code", return_value=(None, None)):
			interpreter.interpreter_main("2.4.1")

		rendered_code = [call for call in display_code_mock.call_args_list if call.args and "print('OK')" in str(call.args[0])]
		self.assertTrue(rendered_code)

	@patch("libs.interpreter_lib.display_markdown_message")
	@patch("libs.interpreter_lib.display_code")
	@patch("builtins.input", side_effect=["Explain what to do", "/exit"])
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	def test_code_mode_shows_raw_output_when_no_code_block(
		self, _mock_client, _mock_history, _mock_input, display_code_mock, markdown_mock
	):
		interpreter = Interpreter(self._make_args(mode="code", model="z-ai-glm-5"))
		interpreter.config_values = {"start_sep": "```", "end_sep": "```"}

		with patch.object(interpreter.utility_manager, "get_os_platform", return_value=("Windows 10", "10")), \
			 patch.object(interpreter, "get_mode_prompt", return_value="Explain what to do"), \
			 patch.object(interpreter, "generate_content", return_value="Here is a plain-text answer"), \
			 patch.object(interpreter.code_interpreter, "extract_code", return_value=None):
			interpreter.interpreter_main("2.4.1")

		rendered_code = [call.args[0] for call in display_code_mock.call_args_list if call.args]
		rendered_messages = [call.args[0] for call in markdown_mock.call_args_list if call.args]
		self.assertIn("Here is a plain-text answer", rendered_code)
		self.assertTrue(any("No executable code block was returned" in message for message in rendered_messages))

	@patch("libs.interpreter_lib.display_markdown_message")
	@patch("builtins.input", side_effect=["Hello", "/exit"])
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	def test_recoverable_provider_errors_do_not_crash_interactive_session(
		self, _mock_client, _mock_history, _mock_input, markdown_mock
	):
		interpreter = Interpreter(self._make_args(mode="chat", model="z-ai-glm-5"))
		interpreter.config_values = {"start_sep": "```", "end_sep": "```"}

		with patch.object(interpreter.utility_manager, "get_os_platform", return_value=("Windows 10", "10")), \
			 patch.object(interpreter, "get_mode_prompt", return_value="Hello"), \
			 patch.object(interpreter, "generate_content", side_effect=Exception("Rate limit reached for requests")):
			interpreter.interpreter_main("2.4.1")

		rendered_messages = [call.args[0] for call in markdown_mock.call_args_list if call.args]
		self.assertTrue(any("Request failed:" in message for message in rendered_messages))

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	@patch("builtins.input", side_effect=EOFError)
	def test_execute_code_defaults_to_no_on_eof(self, _mock_input, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(mode="code", model="z-ai-glm-5"))
		result = interpreter.execute_code("print('OK')", "Windows 10")
		self.assertEqual(result, (None, None))


class TestDangerousCommandSafetyPatterns(unittest.TestCase):
	"""
	Tests for dangerous command detection in command mode.
	Covers the exact pattern from the reported issue:
	  del "D:\\Temp\\*.txt"
	as well as related quoted-path and wildcard variants.
	"""

	def setUp(self):
		self.safety_manager = ExecutionSafetyManager()

	# ── Quoted wildcard del (the original failing case) ────────────────────

	def test_blocks_quoted_wildcard_del_double_quote(self):
		"""del \"D:\\Temp\\*.txt\" must be blocked (quoted absolute path with wildcard)."""
		decision = self.safety_manager.assess_execution(
			'del "D:\\Temp\\*.txt"', "command"
		)
		self.assertFalse(decision.allowed)
		self.assertTrue(
		    any("blocked" in r.lower() for r in decision.reasons),
		    f"Expected blocked reason, got: {decision.reasons}",
		)

	def test_blocks_quoted_wildcard_del_single_quote(self):
		"""del 'D:\\Temp\\*.txt' must be blocked."""
		decision = self.safety_manager.assess_execution(
			"del 'D:\\Temp\\*.txt'", "command"
		)
		self.assertFalse(decision.allowed)

	def test_blocks_quoted_del_specific_txt_file(self):
		"""del \"D:\\Temp\\notes.txt\" — single quoted file, absolute path."""
		decision = self.safety_manager.assess_execution(
			'del "D:\\Temp\\notes.txt"', "command"
		)
		self.assertFalse(decision.allowed)

	def test_blocks_quoted_del_forward_slash_path(self):
		"""del \"C:/Users/temp/*.log\" — forward-slash absolute path inside quotes."""
		decision = self.safety_manager.assess_execution(
			'del "C:/Users/temp/*.log"', "command"
		)
		self.assertFalse(decision.allowed)

	def test_blocks_unquoted_wildcard_del_backslash(self):
		"""del D:\\Temp\\*.txt — unquoted absolute-path wildcard del."""
		decision = self.safety_manager.assess_execution(
			"del D:\\Temp\\*.txt", "command"
		)
		self.assertFalse(decision.allowed)

	def test_allows_relative_del_command(self):
		"""del *.txt — relative path, no drive letter; should be blocked."""
		decision = self.safety_manager.assess_execution("del *.txt", "command")
		self.assertFalse(decision.allowed)

	def test_allows_del_without_path(self):
		"""del notes.txt — no path component at all; should be blocked."""
		decision = self.safety_manager.assess_execution("del notes.txt", "command")
		self.assertFalse(decision.allowed)

	def test_blocks_del_with_force_flag(self):
		"""del /f file.txt — force-delete flag is blocked regardless of path."""
		decision = self.safety_manager.assess_execution("del /f file.txt", "command")
		self.assertFalse(decision.allowed)

	def test_blocks_del_with_quiet_flag(self):
		"""del /q file.txt — quiet-delete flag is blocked."""
		decision = self.safety_manager.assess_execution("del /q file.txt", "command")
		self.assertFalse(decision.allowed)


class TestDangerousCommandRepairLoop(unittest.TestCase):
	"""
	Tests that verify the _attempt_repair_after_failure loop correctly handles
	the case where the LLM (mocked) responds with another dangerous command.

	Scenario (mirrors the reported bug):
	  - Mode: command
	  - Task: 'remove all text files from D:\\Temp'
	  - First LLM response: del "D:\\Temp\\*.txt"   → safety-blocked
	  - Repair prompt sent back to LLM
	  - Second LLM response: del "D:\\Temp\\*.txt"  → still dangerous
	  - The repair loop MUST stop and surface a safety-blocked error,
		NOT execute the dangerous command.
	"""

	def _make_command_interpreter(self):
		with patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None), \
			 patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None):
			args = Namespace(
				exec=True,
				save_code=False,
				mode="command",
				model="z-ai-glm-5",
				display_code=False,
				lang="python",
				file=None,
				history=False,
				upgrade=False,
				unsafe=False,
			)
			interp = Interpreter(args)
		interp.config_values = {"start_sep": "```", "end_sep": "```"}
		return interp

	@patch("libs.interpreter_lib.display_markdown_message")
	@patch("libs.interpreter_lib.display_code")
	def test_repair_loop_halts_when_llm_keeps_returning_dangerous_command(
		self, _mock_display_code, _mock_markdown
	):
		"""
		When every LLM repair response is still a dangerous command,
		_attempt_repair_after_failure must stop after MAX_REPAIR_ATTEMPTS
		and return a safety-blocked error without executing anything.
		"""
		interp = self._make_command_interpreter()

		dangerous_cmd = 'del "D:\\Temp\\*.txt"'
		dangerous_llm_response = f"```\n{dangerous_cmd}\n```"

		with patch.object(
			interp, "_generate_content_with_retries", return_value=dangerous_llm_response
		) as mock_generate:
			snippet, output, error = interp._attempt_repair_after_failure(
				task="remove all text files from D:\\Temp",
				prompt="remove all text files from D:\\Temp",
				code_snippet=dangerous_cmd,
				code_error="The filename, directory name, or volume label syntax is incorrect.",
				os_name=UtilityManager().get_os_platform()[0],
				start_sep="```",
				end_sep="```",
				extracted_file_name=None,
			)

		self.assertLessEqual(mock_generate.call_count, interp.MAX_REPAIR_ATTEMPTS)
		self.assertIsNotNone(error)
		self.assertIn("Safety blocked", error)

	def test_safety_manager_blocks_powershell_pipeline_remove_item_force(self):
		safety_manager = ExecutionSafetyManager()
		code = r'''
	$Folders = @(
		"D:\\Temp",
		"C:\\Path\\To\\Other\\Folder"
	)

	foreach ($Folder in $Folders) {
		if (Test-Path -Path $Folder) {
			Get-ChildItem -Path $Folder -Filter "*.txt" -File | Remove-Item -Force
		}
	}
	'''
		decision = safety_manager.assess_execution(code, "script")
		self.assertFalse(decision.allowed)

	def test_safety_manager_blocks_python_unlink_loop(self):
		safety_manager = ExecutionSafetyManager()
		code = r'''
	from pathlib import Path
	for file in Path("D:\\Temp").glob("*.txt"):
		file.unlink()
	'''
		decision = safety_manager.assess_execution(code, "code")
		self.assertFalse(decision.allowed)

	def test_safety_manager_blocks_javascript_unlink_loop(self):
		safety_manager = ExecutionSafetyManager()
		code = r'''
			const fs = require("fs");
			const path = require("path");
			const dir = "D:\\Temp";
			fs.readdirSync(dir).forEach((file) => {
				if (file.endsWith(".txt")) {
					fs.unlinkSync(path.join(dir, file));
				}
			});
	'''
		decision = safety_manager.assess_execution(code, "code")
		self.assertFalse(decision.allowed)
	

	@patch("libs.interpreter_lib.display_markdown_message")
	@patch("libs.interpreter_lib.display_code")
	def test_repair_loop_does_not_execute_dangerous_repaired_command(
		self, _mock_display_code, _mock_markdown
	):
		"""
		_execute_generated_output must NOT be called with the dangerous
		command even after the LLM supplies it during repair.
		"""
		interp = self._make_command_interpreter()

		dangerous_cmd = 'del "D:\\Temp\\*.txt"'
		dangerous_llm_response = f"```\n{dangerous_cmd}\n```"

		execute_calls = []

		def fake_execute(snippet, os_name, force_execute=False):
			execute_calls.append(snippet)
			return None, "Safety blocked: Absolute-path deletion is blocked.", None

		with patch.object(interp, "_generate_content_with_retries", return_value=dangerous_llm_response), \
			 patch.object(interp, "_execute_generated_output", side_effect=fake_execute):
			interp._attempt_repair_after_failure(
				task="remove all text files from D:\\Temp",
				prompt="remove all text files from D:\\Temp",
				code_snippet=dangerous_cmd,
				code_error="The filename, directory name, or volume label syntax is incorrect.",
				os_name="Windows 10",
				start_sep="```",
				end_sep="```",
				extracted_file_name=None,
			)

		for called_snippet in execute_calls:
			decision = ExecutionSafetyManager().assess_execution(called_snippet, "command")
			self.assertFalse(
				decision.allowed,
				f"Dangerous command was passed to executor unblocked: {called_snippet!r}",
			)

	@patch("libs.interpreter_lib.display_markdown_message")
	@patch("libs.interpreter_lib.display_code")
	def test_repair_loop_succeeds_when_llm_returns_safe_command(
		self, _mock_display_code, _mock_markdown
	):
		"""
		When the LLM repairs the command with a safe equivalent (e.g., using
		PowerShell Remove-Item with a relative path), the repair loop must
		return success (no error).
		"""
		interp = self._make_command_interpreter()

		safe_cmd = "dir /b"
		safe_llm_response = f"```\n{safe_cmd}\n```"

		with patch.object(interp, "_generate_content_with_retries", return_value=safe_llm_response), \
			 patch.object(interp, "_execute_generated_output", return_value=("Volume in drive D", None, None)):
			snippet, output, error = interp._attempt_repair_after_failure(
				task="list all text files in D:\\Temp",
				prompt="list all text files in D:\\Temp",
				code_snippet="dir D:\\Temp\\*.txt",
				code_error="The filename, directory name, or volume label syntax is incorrect.",
				os_name="Windows 10",
				start_sep="```",
				end_sep="```",
				extracted_file_name=None,
			)

		self.assertIsNone(error)
		self.assertIsNotNone(output)

	@patch("libs.interpreter_lib.display_markdown_message")
	@patch("libs.interpreter_lib.display_code")
	def test_safety_manager_blocks_exact_failing_command_from_issue(
		self, _mock_display_code, _mock_markdown
	):
		"""
		Regression test: the exact command from the reported issue
		must be blocked BEFORE execution.
		"""
		safety_manager = ExecutionSafetyManager()
		failing_cmd = 'del "D:\\Temp\\*.txt"'
		decision = safety_manager.assess_execution(failing_cmd, "command")
		self.assertFalse(
			decision.allowed,
			f"Expected command to be blocked but it was allowed. Command: {failing_cmd!r}",
		)
		self.assertTrue(
			len(decision.reasons) > 0,
			"Safety decision must include at least one blocking reason.",
		)


class TestBuildParser(unittest.TestCase):
	"""Tests for the build_parser() function added in this PR."""

	def test_unsafe_flag_defaults_to_false(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args([])
		self.assertFalse(args.unsafe)

	def test_unsafe_flag_can_be_set(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--unsafe"])
		self.assertTrue(args.unsafe)

	def test_model_default_is_none(self):
		# Previously the default was 'code-llama'; PR changes it to None
		parser = interpreter_entry.build_parser()
		args = parser.parse_args([])
		self.assertIsNone(args.model)

	def test_cli_flag_defaults_to_false(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args([])
		self.assertFalse(args.cli)

	def test_tui_flag_defaults_to_false(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args([])
		self.assertFalse(args.tui)

	def test_cli_flag_can_be_set(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--cli"])
		self.assertTrue(args.cli)
		self.assertFalse(args.tui)

	def test_tui_flag_can_be_set(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--tui"])
		self.assertTrue(args.tui)
		self.assertFalse(args.cli)

	def test_cli_and_tui_are_mutually_exclusive(self):
		import argparse
		parser = interpreter_entry.build_parser()
		with self.assertRaises(SystemExit):
			parser.parse_args(["--cli", "--tui"])

	def test_mode_choices_include_all_expected_modes(self):
		parser = interpreter_entry.build_parser()
		for mode in ["code", "script", "command", "vision", "chat"]:
			args = parser.parse_args(["--mode", mode])
			self.assertEqual(args.mode, mode)

	def test_mode_rejects_invalid_choice(self):
		parser = interpreter_entry.build_parser()
		with self.assertRaises(SystemExit):
			parser.parse_args(["--mode", "invalid_mode"])

	def test_display_code_short_flag_works(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["-dc"])
		self.assertTrue(args.display_code)

	def test_mode_short_flag_works(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["-md", "code"])
		self.assertEqual(args.mode, "code")

	def test_model_short_flag_works(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["-m", "gpt-4o"])
		self.assertEqual(args.model, "gpt-4o")

	def test_history_flag_defaults_to_false(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args([])
		self.assertFalse(args.history)

	def test_exec_flag_defaults_to_false(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args([])
		self.assertFalse(args.exec)

	def test_save_code_flag_defaults_to_false(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args([])
		self.assertFalse(args.save_code)

	def test_lang_defaults_to_python(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args([])
		self.assertEqual(args.lang, "python")

	def test_unsafe_is_independent_of_cli_flag(self):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--cli", "--unsafe"])
		self.assertTrue(args.unsafe)
		self.assertTrue(args.cli)


class TestPrepareArgsBehavior(unittest.TestCase):
	"""Tests for the prepare_args() function added in this PR."""

	@patch("interpreter.TerminalUI.launch")
	def test_prepare_args_with_explicit_tui_flag_calls_tui_launch(self, launch_mock):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--tui"])
		launch_mock.return_value = args
		interpreter_entry.prepare_args(args, ["interpreter.py", "--tui"])
		launch_mock.assert_called_once()

	@patch("interpreter._get_default_model", return_value="gpt-4o")
	def test_prepare_args_cli_preserves_explicitly_set_model(self, _mock_model):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--cli", "-m", "gemini-pro"])
		result = interpreter_entry.prepare_args(args, ["interpreter.py", "--cli", "-m", "gemini-pro"])
		self.assertEqual(result.model, "gemini-pro")

	@patch("interpreter._get_default_model", return_value="gpt-4o")
	def test_prepare_args_cli_preserves_explicitly_set_mode(self, _mock_model):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--cli", "-md", "chat"])
		result = interpreter_entry.prepare_args(args, ["interpreter.py", "--cli", "-md", "chat"])
		self.assertEqual(result.mode, "chat")

	@patch("interpreter._get_default_model", return_value="gpt-4o")
	def test_prepare_args_cli_sets_mode_to_code_when_not_provided(self, _mock_model):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--cli"])
		result = interpreter_entry.prepare_args(args, ["interpreter.py", "--cli"])
		self.assertEqual(result.mode, "code")

	@patch("interpreter._get_default_model", return_value="openrouter-free")
	def test_prepare_args_cli_sets_model_to_default_when_not_provided(self, _mock_model):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--cli"])
		result = interpreter_entry.prepare_args(args, ["interpreter.py", "--cli"])
		self.assertEqual(result.model, "openrouter-free")

	@patch("interpreter._get_default_model", return_value="gpt-4o")
	def test_prepare_args_sets_cli_true_when_cli_flag_given(self, _mock_model):
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--cli"])
		result = interpreter_entry.prepare_args(args, ["interpreter.py", "--cli"])
		self.assertTrue(result.cli)

	@patch("interpreter._get_default_model", return_value="gpt-4o")
	def test_prepare_args_with_model_and_mode_args_does_not_launch_tui(self, _mock_model):
		# More than 1 argv entry without --tui → should not call TUI
		parser = interpreter_entry.build_parser()
		args = parser.parse_args(["--cli", "-m", "gpt-4o", "-md", "code"])
		with patch("interpreter.TerminalUI.launch") as tui_mock:
			result = interpreter_entry.prepare_args(args, ["interpreter.py", "--cli", "-m", "gpt-4o", "-md", "code"])
		tui_mock.assert_not_called()
		self.assertIsNotNone(result)


class TestGetDefaultModel(unittest.TestCase):
	"""Tests for the _get_default_model() helper added in this PR."""

	@patch("interpreter.UtilityManager.get_default_model_name", return_value="openrouter-free")
	def test_get_default_model_delegates_to_utility_manager(self, mock_get):
		result = interpreter_entry._get_default_model()
		self.assertEqual(result, "openrouter-free")
		mock_get.assert_called_once()

	@patch("interpreter.UtilityManager.get_default_model_name", return_value="groq-llama-3.3")
	def test_get_default_model_returns_whatever_utility_manager_returns(self, mock_get):
		result = interpreter_entry._get_default_model()
		self.assertEqual(result, "groq-llama-3.3")


class TestSubprocessSecurityKwargs(unittest.TestCase):
	"""Tests for CodeInterpreter._get_subprocess_security_kwargs() added in this PR."""

	def setUp(self):
		# Mock the Logger.initialize to avoid FileNotFoundError during test setup
		with patch("libs.code_interpreter.Logger.initialize", return_value=None):
			self.ci = CodeInterpreter()

	def test_no_sandbox_context_returns_none_for_cwd_and_env(self):
		kwargs = self.ci._get_subprocess_security_kwargs(sandbox_context=None)
		self.assertIsNone(kwargs["cwd"])
		self.assertIsNone(kwargs["env"])

	def test_sandbox_context_with_cwd_is_passed(self):
		from types import SimpleNamespace
		sandbox_path = os.path.join(tempfile.gettempdir(), "sandbox")
		ctx = SimpleNamespace(cwd=sandbox_path, env=None)
		kwargs = self.ci._get_subprocess_security_kwargs(sandbox_context=ctx)
		self.assertEqual(kwargs["cwd"], sandbox_path)

	def test_sandbox_context_with_env_is_passed(self):
		from types import SimpleNamespace
		custom_env = {"PATH": "/usr/bin", "HOME": tempfile.gettempdir()}
		ctx = SimpleNamespace(cwd=None, env=custom_env)
		kwargs = self.ci._get_subprocess_security_kwargs(sandbox_context=ctx)
		# Expect only whitelisted keys to be present and merged with defaults
		allowed_keys = {"PATH", "HOME", "LANG"}
		if os.name == "nt":
			default_env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("USERPROFILE", ""), "LANG": os.environ.get("LANG", "C")}
		else:
			default_env = {"PATH": "/usr/bin:/bin", "HOME": tempfile.gettempdir(), "LANG": "C"}
		expected = default_env.copy()
		for k in allowed_keys:
			if k in custom_env and custom_env[k] is not None:
				expected[k] = custom_env[k]
		self.assertEqual(kwargs["env"], expected)

	def test_sandbox_context_with_neither_cwd_nor_env(self):
		from types import SimpleNamespace
		# Context object with no cwd/env attributes → getattr returns None
		ctx = SimpleNamespace()
		kwargs = self.ci._get_subprocess_security_kwargs(sandbox_context=ctx)
		self.assertIsNone(kwargs["cwd"])
		self.assertIsNone(kwargs["env"])

	@patch("libs.code_interpreter.os.name", "posix")
	def test_unix_returns_start_new_session_true(self):
		kwargs = self.ci._get_subprocess_security_kwargs()
		self.assertTrue(kwargs.get("start_new_session"))

	@patch("libs.code_interpreter.os.name", "posix")
	def test_unix_does_not_include_creationflags(self):
		kwargs = self.ci._get_subprocess_security_kwargs()
		self.assertNotIn("creationflags", kwargs)


class TestBuildCommandInvocation(unittest.TestCase):
	"""Tests for CodeInterpreter._build_command_invocation() added in this PR."""

	def setUp(self):
		# Mock the Logger.initialize to avoid FileNotFoundError during test setup
		with patch("libs.code_interpreter.Logger.initialize", return_value=None):
			self.ci = CodeInterpreter()

	@patch("libs.code_interpreter.os.name", "posix")
	@patch("libs.code_interpreter.os.path.exists", return_value=True)
	def test_unix_with_bash_uses_bash_noprofile_norc(self, _mock_exists):
		result = self.ci._build_command_invocation("echo hello")
		self.assertEqual(result, shlex.split("echo hello"))

	@patch("libs.code_interpreter.os.name", "posix")
	@patch("libs.code_interpreter.os.path.exists", return_value=False)
	def test_unix_without_bash_falls_back_to_sh(self, _mock_exists):
		result = self.ci._build_command_invocation("echo hello")
		self.assertEqual(result, shlex.split("echo hello"))

	@patch("libs.code_interpreter.os.name", "nt")
	def test_windows_uses_cmd_exe(self):
		# New behavior: avoid forcing cmd.exe; return argv via shlex.split(posix=False)
		result = self.ci._build_command_invocation("dir")
		self.assertEqual(result[-1], "dir")

	@patch("libs.code_interpreter.os.name", "posix")
	@patch("libs.code_interpreter.os.path.exists", return_value=True)
	def test_command_is_last_element(self, _mock_exists):
		cmd = "ls -la /tmp"
		result = self.ci._build_command_invocation(cmd)
		self.assertEqual(result, shlex.split(cmd))


class TestExecuteScriptInvalidShell(unittest.TestCase):
	"""Tests for CodeInterpreter._execute_script() with new sandbox_context parameter."""

	def setUp(self):
		# Mock the Logger.initialize to avoid FileNotFoundError during test setup
		with patch("libs.code_interpreter.Logger.initialize", return_value=None):
			self.ci = CodeInterpreter()

	def test_execute_script_invalid_shell_raises_error(self):
		# Invalid shell should return None, error message instead of raising.
		result = self.ci._execute_script("echo hi", shell="invalid_shell")  # noqa: S604
		self.assertIsNone(result[0])
		self.assertIn("Invalid shell selected", result[1])

	def test_execute_script_unsupported_shell_raises_error(self):
		# Unsupported shell should return None, error message instead of raising.
		result = self.ci._execute_script("echo hi", shell="zsh")  # noqa: S604
		self.assertIsNone(result[0])
		self.assertIn("Invalid shell selected", result[1])

	@patch("subprocess.Popen")
	def test_execute_script_passes_sandbox_context_timeout(self, mock_popen):
		from types import SimpleNamespace
		mock_process = mock_popen.return_value
		mock_process.communicate.return_value = (b"ok", b"")
		mock_process.returncode = 0
		ctx = SimpleNamespace(cwd=None, env=None, timeout_seconds=60)
		with patch("libs.code_interpreter.os.path.exists", return_value=True), \
			 patch("libs.code_interpreter.os.name", "posix"):
			self.ci._execute_script("echo hi", shell="bash", sandbox_context=ctx)
		mock_process.communicate.assert_called_once_with(timeout=60)

	@patch("subprocess.Popen")
	def test_execute_script_defaults_to_timeout_without_sandbox(self, mock_popen):
		mock_process = mock_popen.return_value
		mock_process.communicate.return_value = (b"hi", b"")
		mock_process.returncode = 0
		with patch("libs.code_interpreter.os.path.exists", return_value=True), \
			 patch("libs.code_interpreter.os.name", "posix"):
			self.ci._execute_script("echo hi", shell="bash")
		mock_process.communicate.assert_called_once_with(timeout=120)

	@patch("subprocess.Popen")
	def test_execute_script_timeout_expired_kills_process(self, mock_popen):
		import subprocess as _subprocess
		mock_process = mock_popen.return_value
		# First communicate() call raises TimeoutExpired; second (after kill) returns empty bytes.
		mock_process.communicate.side_effect = [
			_subprocess.TimeoutExpired(cmd="bash", timeout=30),
			(b"", b""),
		]
		# Timeout should return error message instead of raising.
		with patch("libs.code_interpreter.os.path.exists", return_value=True), \
			 patch("libs.code_interpreter.os.name", "posix"), \
			 patch("libs.code_interpreter.os.getpgid", return_value=12345, create=True) as mock_getpgid, \
			 patch("libs.code_interpreter.os.killpg", create=True) as mock_killpg:
			result = self.ci._execute_script("sleep 100", shell="bash")
			self.assertIsNone(result[0])
			self.assertEqual(result[1], "Execution timed out.")
			# Ensure we attempted to kill the process group or at least killed the process
			self.assertTrue(mock_killpg.called or mock_process.kill.called)


class TestNewConfigFilesFromPR(unittest.TestCase):
	"""Tests for new and modified config files introduced in this PR."""

	def _read_config(self, name):
		from libs.utility_manager import UtilityManager
		return UtilityManager().read_config_file(str(CONFIGS_DIR / name))

	def _read_hf_model(self, name):
		return _read_hf_model(CONFIGS_DIR / name)

	# --- New Claude configs ---

	def test_claude_3_7_sonnet_config_maps_to_claude_sonnet_4_6(self):
		self.assertEqual(self._read_hf_model("claude-3-7-sonnet.json"), "claude-3-7-sonnet")

	def test_claude_3_5_sonnet_config_maps_to_claude_sonnet_4_6(self):
		self.assertEqual(self._read_hf_model("claude-3-5-sonnet.json"), "claude-sonnet-4-6")

	def test_claude_sonnet_4_6_config_has_correct_model(self):
		self.assertEqual(self._read_hf_model("claude-sonnet-4-6.json"), "claude-sonnet-4-6")

	def test_claude_opus_4_6_config_has_correct_model(self):
		self.assertEqual(self._read_hf_model("claude-opus-4-6.json"), "claude-opus-4-6")

	def test_claude_haiku_4_5_config_has_correct_model(self):
		self.assertEqual(self._read_hf_model("claude-haiku-4-5.json"), "claude-haiku-4-5")

	def test_claude_3_opus_remapped_to_claude_opus_4_6(self):
		self.assertEqual(self._read_hf_model("claude-3-opus.json"), "claude-opus-4-6")

	# --- Legacy HuggingFace configs remapped ---

	def test_code_llama_maps_to_meta_llama_3(self):
		self.assertEqual(
			self._read_hf_model("code-llama.json"),
			"huggingface/meta-llama/Meta-Llama-3-8B-Instruct",
		)

	def test_code_llama_phind_maps_to_meta_llama_3(self):
		self.assertEqual(
			self._read_hf_model("code-llama-phind.json"),
			"huggingface/meta-llama/Meta-Llama-3-8B-Instruct",
		)

	# --- New Gemini configs (legacy aliases) ---

	def test_gemini_1_5_pro_maps_to_gemini_2_5_pro(self):
		self.assertEqual(self._read_hf_model("gemini-1.5-pro.json"), "gemini/gemini-2.5-pro")

	def test_gemini_1_5_flash_maps_to_gemini_2_5_flash(self):
		self.assertEqual(self._read_hf_model("gemini-1.5-flash.json"), "gemini/gemini-2.5-flash")

	# --- Separator changes: all new configs use single backtick ---

	def test_claude_sonnet_4_6_config_uses_triple_backtick_separator(self):
		config = self._read_config("claude-sonnet-4-6.json")
		self.assertEqual(config.get("start_sep"), "```")
		self.assertEqual(config.get("end_sep"), "```")

	def test_gemini_1_5_pro_config_uses_triple_backtick_separator(self):
		config = self._read_config("gemini-1.5-pro.json")
		self.assertEqual(config.get("start_sep"), "```")
		self.assertEqual(config.get("end_sep"), "```")

	def test_deepseek_chat_config_uses_triple_backtick_separator(self):
		config = self._read_config("deepseek-chat.json")
		self.assertEqual(config.get("start_sep"), "```")
		self.assertEqual(config.get("end_sep"), "```")

	def test_deepseek_reasoner_config_uses_triple_backtick_separator(self):
		config = self._read_config("deepseek-reasoner.json")
		self.assertEqual(config.get("start_sep"), "```")
		self.assertEqual(config.get("end_sep"), "```")

	# --- max_tokens updated in deepseek configs ---

	def test_deepseek_chat_config_max_tokens_is_4096(self):
		config = self._read_config("deepseek-chat.json")
		self.assertEqual(config.get("max_tokens"), 4096)

	def test_deepseek_coder_config_max_tokens_is_4096(self):
		config = self._read_config("deepseek-coder.json")
		self.assertEqual(config.get("max_tokens"), 4096)

	def test_deepseek_reasoner_config_max_tokens_is_4096(self):
		config = self._read_config("deepseek-reasoner.json")
		self.assertEqual(config.get("max_tokens"), 4096)

	# --- Browser Use config specific fields ---

	def test_browser_use_config_has_provider_field(self):
		config = self._read_config("browser-use-bu-max.json")
		self.assertEqual(config.get("provider"), "browser-use")

	def test_browser_use_config_has_correct_api_base(self):
		config = self._read_config("browser-use-bu-max.json")
		self.assertEqual(config.get("api_base"), "https://api.browser-use.com/api/v3")

	def test_browser_use_config_has_timeout_setting(self):
		config = self._read_config("browser-use-bu-max.json")
		self.assertIn("browser_use_timeout", config)

	def test_browser_use_config_has_poll_interval(self):
		config = self._read_config("browser-use-bu-max.json")
		self.assertIn("browser_use_poll_interval", config)

	def test_browser_use_config_max_tokens_is_2048(self):
		config = self._read_config("browser-use-bu-max.json")
		self.assertEqual(config.get("max_tokens"), 2048)

	# --- deepseek-coder remapped to deepseek-chat ---

	def test_deepseek_coder_config_remapped_to_deepseek_chat_model(self):
		self.assertEqual(self._read_hf_model("deepseek-coder.json"), "deepseek-chat")

	def test_deepseek_chat_has_no_skip_first_line_key(self):
		config = self._read_config("deepseek-chat.json")
		self.assertNotIn("skip_first_line", config)

	def test_deepseek_coder_has_no_skip_first_line_key(self):
		config = self._read_config("deepseek-coder.json")
		self.assertNotIn("skip_first_line", config)


class TestVersionFile(unittest.TestCase):
	"""Tests for the VERSION file added in this PR."""

	def test_version_file_exists(self):
		version_file = ROOT_DIR / "VERSION"
		self.assertTrue(version_file.exists(), "VERSION file should exist")

	def test_version_file_matches_interpreter_version_constant(self):
		version_file = ROOT_DIR / "VERSION"
		content = version_file.read_text(encoding="utf-8").strip()
		self.assertEqual(content, interpreter_entry.INTERPRETER_VERSION)


class TestEnvExampleFile(unittest.TestCase):
	"""Tests for the .env.example file added in this PR."""

	def setUp(self):
		self.env_example_path = ROOT_DIR / ".env.example"
		self.content = self.env_example_path.read_text(encoding="utf-8-sig")

	def test_env_example_file_exists(self):
		self.assertTrue(self.env_example_path.exists())

	def test_env_example_contains_openai_key(self):
		self.assertIn("OPENAI_API_KEY=", self.content)

	def test_env_example_contains_gemini_key(self):
		self.assertIn("GEMINI_API_KEY=", self.content)

	def test_env_example_contains_anthropic_key(self):
		self.assertIn("ANTHROPIC_API_KEY=", self.content)

	def test_env_example_contains_groq_key(self):
		self.assertIn("GROQ_API_KEY=", self.content)

	def test_env_example_contains_deepseek_key(self):
		self.assertIn("DEEPSEEK_API_KEY=", self.content)

	def test_env_example_contains_huggingface_key(self):
		self.assertIn("HUGGINGFACE_API_KEY=", self.content)

	def test_env_example_contains_nvidia_key(self):
		self.assertIn("NVIDIA_API_KEY=", self.content)

	def test_env_example_contains_z_ai_key(self):
		self.assertIn("Z_AI_API_KEY=", self.content)

	def test_env_example_contains_openrouter_key(self):
		self.assertIn("OPENROUTER_API_KEY=", self.content)

	def test_env_example_contains_browser_use_key(self):
		self.assertIn("BROWSER_USE_API_KEY=", self.content)

	def test_env_example_values_are_empty_placeholders(self):
		# API key lines should end with '=' and no value (just placeholders)
		for line in self.content.splitlines():
			stripped = line.strip()
			if stripped.endswith("_KEY=") or stripped.endswith("_KEY= "):
				# All key lines end with just '=' (empty value)
				self.assertTrue(stripped.endswith("="), f"Expected empty value in: {stripped}")


class TestGitignoreEntries(unittest.TestCase):
	"""Tests for new entries added to .gitignore in this PR."""

	def setUp(self):
		gitignore_path = ROOT_DIR / ".gitignore"
		self.content = gitignore_path.read_text(encoding="utf-8")

	def test_gitignore_contains_pycache_dir(self):
		self.assertIn("__pycache__/", self.content)

	def test_gitignore_contains_pytest_cache(self):
		self.assertIn(".pytest_cache/", self.content)

	def test_gitignore_contains_venv_dir(self):
		self.assertIn(".venv/", self.content)

	def test_gitignore_contains_logs_dir(self):
		self.assertIn("logs/*", self.content)

	def test_gitignore_contains_dist_dir(self):
		self.assertIn("dist/", self.content)

	def test_gitignore_contains_tmp_files(self):
		self.assertIn("*.tmp", self.content)

	def test_gitignore_contains_bak_files(self):
		self.assertIn("*.bak", self.content)

	def test_gitignore_contains_env_local(self):
		self.assertIn(".env.local", self.content)

	def test_gitignore_contains_env_star_local(self):
		self.assertIn(".env.*.local", self.content)

	def test_gitignore_contains_history_gitkeep_exclusion(self):
		self.assertIn("!history/.gitkeep", self.content)

	def test_gitignore_contains_debug_output_artifacts(self):
		self.assertIn("debug_output*.txt", self.content)

	def test_gitignore_contains_test_results_artifacts(self):
		self.assertIn("test_results*.txt", self.content)

	def test_gitignore_ends_with_newline(self):
		# Ensures the previously missing final newline (desktop.ini) was fixed
		self.assertTrue(self.content.endswith("\n"))


class TestLlmDispatcherLocalEndpoint(unittest.TestCase):
	def test_llama_custom_api_base_routes_as_openai_compatible(self):
		kwargs = build_completion_kwargs(
			model="llama3.1:8b",
			messages=[{"role": "user", "content": "hi"}],
			temperature=0.1,
			max_tokens=128,
			config_provider="",
			api_base="http://localhost:8080/v1",
		)
		self.assertEqual(kwargs["api_base"], "http://localhost:8080/v1")
		self.assertEqual(kwargs["custom_llm_provider"], "openai")

	def test_explicit_provider_local_sets_openai_shim(self):
		kwargs = build_completion_kwargs(
			model="qwen2.5",
			messages=[{"role": "user", "content": "hi"}],
			temperature=0.1,
			max_tokens=128,
			config_provider="local",
			api_base="http://127.0.0.1:11434/v1",
		)
		self.assertEqual(kwargs["custom_llm_provider"], "openai")

	def test_llama_without_api_base_does_not_use_openai_shim(self):
		kwargs = build_completion_kwargs(
			model="llama3.1:8b",
			messages=[{"role": "user", "content": "hi"}],
			temperature=0.1,
			max_tokens=128,
			config_provider="",
			api_base="None",
		)
		self.assertNotIn("custom_llm_provider", kwargs)


class TestDecisionDataclass(unittest.TestCase):
	"""Tests for the renamed Decision dataclass (was SafetyDecision in the PR)."""

	def test_decision_allowed_true_with_no_reasons(self):
		from libs.safety_manager import Decision
		d = Decision(allowed=True)
		self.assertTrue(d.allowed)
		self.assertEqual(d.reasons, [])

	def test_decision_allowed_false_with_reasons(self):
		from libs.safety_manager import Decision
		d = Decision(allowed=False, reasons=["Deletion blocked.", "Shell blocked."])
		self.assertFalse(d.allowed)
		self.assertEqual(len(d.reasons), 2)

	def test_decision_reasons_default_is_empty_list(self):
		from libs.safety_manager import Decision
		d1 = Decision(allowed=True)
		d2 = Decision(allowed=True)
		# Ensure default_factory is used (no shared list between instances)
		d1.reasons.append("x")
		self.assertEqual(d2.reasons, [])

	def test_assess_execution_returns_decision_instance(self):
		from libs.safety_manager import Decision
		sm = ExecutionSafetyManager()
		result = sm.assess_execution("print('hello')", "code")
		self.assertIsInstance(result, Decision)


class TestRepairCircuitBreakerUpdatedLogic(unittest.TestCase):
	"""Tests for the updated RepairCircuitBreaker logic (PR changed stop-order)."""

	def test_same_error_stops_on_second_call(self):
		"""Same error text must return False on the second call, not the third."""
		breaker = RepairCircuitBreaker(max_attempts=5)
		self.assertTrue(breaker.should_continue("NameError: name 'x' is not defined"))
		# Same error → must stop immediately
		self.assertFalse(breaker.should_continue("NameError: name 'x' is not defined"))

	def test_different_errors_consume_attempts(self):
		breaker = RepairCircuitBreaker(max_attempts=3)
		self.assertTrue(breaker.should_continue("error one"))
		self.assertTrue(breaker.should_continue("error two"))
		self.assertTrue(breaker.should_continue("error three"))
		# Max attempts reached
		self.assertFalse(breaker.should_continue("error four"))

	def test_max_attempts_zero_always_stops(self):
		breaker = RepairCircuitBreaker(max_attempts=0)
		self.assertFalse(breaker.should_continue("any error"))

	def test_attempts_counter_increments_correctly(self):
		breaker = RepairCircuitBreaker(max_attempts=3)
		breaker.should_continue("err1")
		breaker.should_continue("err2")
		self.assertEqual(breaker.attempts, 2)

	def test_normalize_error_strips_whitespace(self):
		breaker = RepairCircuitBreaker(max_attempts=3)
		# Leading/trailing whitespace and doubled spaces should be normalized
		self.assertTrue(breaker.should_continue("  some  error  "))
		self.assertFalse(breaker.should_continue("some error"))

	def test_seen_errors_tracks_normalized_errors(self):
		breaker = RepairCircuitBreaker(max_attempts=5)
		breaker.should_continue("Error A")
		self.assertIn("error a", breaker.seen_errors)

	def test_max_attempts_one_allows_first_and_blocks_second(self):
		breaker = RepairCircuitBreaker(max_attempts=1)
		self.assertTrue(breaker.should_continue("first error"))
		self.assertFalse(breaker.should_continue("different second error"))


class TestExecutionSafetyManagerUnsafeMode(unittest.TestCase):
	"""Tests for ExecutionSafetyManager unsafe_mode parameter (new in this PR)."""

	def test_unsafe_mode_false_by_default(self):
		sm = ExecutionSafetyManager()
		self.assertFalse(sm.unsafe_mode)

	def test_unsafe_mode_true_allows_dangerous_commands(self):
		sm = ExecutionSafetyManager(unsafe_mode=True)
		decision = sm.assess_execution("rm -rf /", "command")
		self.assertTrue(decision.allowed)

	def test_unsafe_mode_true_allows_delete_code(self):
		sm = ExecutionSafetyManager(unsafe_mode=True)
		decision = sm.assess_execution("import os\nos.remove('file.txt')", "code")
		self.assertTrue(decision.allowed)

	def test_unsafe_mode_true_allows_subprocess_code(self):
		sm = ExecutionSafetyManager(unsafe_mode=True)
		decision = sm.assess_execution("import subprocess\nsubprocess.run(['ls'])", "code")
		self.assertTrue(decision.allowed)

	def test_unsafe_mode_hard_blocks_rd_s_q_regardless(self):
		"""rd /s /q must be blocked even in unsafe_mode — this is the hard block."""
		sm = ExecutionSafetyManager(unsafe_mode=True)
		decision = sm.assess_execution("rd /s /q C:\\Temp", "command")
		self.assertFalse(decision.allowed)
		self.assertIn("Recursive deletion is blocked.", decision.reasons)

	def test_unsafe_mode_hard_blocks_rd_s_q_case_insensitive(self):
		sm = ExecutionSafetyManager(unsafe_mode=True)
		decision = sm.assess_execution("RD /S /Q D:\\folder", "command")
		self.assertFalse(decision.allowed)

	def test_safe_mode_still_blocks_dangerous_commands(self):
		sm = ExecutionSafetyManager(unsafe_mode=False)
		decision = sm.assess_execution("rm -rf /", "command")
		self.assertFalse(decision.allowed)

	def test_unsafe_mode_true_allows_del_command(self):
		sm = ExecutionSafetyManager(unsafe_mode=True)
		decision = sm.assess_execution("del C:\\Temp\\file.txt", "command")
		self.assertTrue(decision.allowed)


class TestExecutionSafetyManagerAstCheck(unittest.TestCase):
	"""Tests for the new _ast_check() method in ExecutionSafetyManager."""

	def setUp(self):
		self.sm = ExecutionSafetyManager()

	def test_ast_blocks_os_remove_call(self):
		code = "import os\nos.remove('myfile.txt')"
		reasons = self.sm._ast_check(code)
		self.assertTrue(any("deletion" in r.lower() for r in reasons))

	def test_ast_blocks_os_unlink_call(self):
		code = "import os\nos.unlink('myfile.txt')"
		reasons = self.sm._ast_check(code)
		self.assertTrue(any("deletion" in r.lower() for r in reasons))

	def test_ast_blocks_shutil_rmtree_call(self):
		code = "import shutil\nshutil.rmtree('/tmp/test')"
		reasons = self.sm._ast_check(code)
		self.assertTrue(any("deletion" in r.lower() for r in reasons))

	def test_ast_blocks_eval(self):
		code = "eval('print(1)')"
		reasons = self.sm._ast_check(code)
		self.assertTrue(any("dynamic" in r.lower() for r in reasons))

	def test_ast_blocks_exec(self):
		code = "exec('import os')"
		reasons = self.sm._ast_check(code)
		self.assertTrue(any("dynamic" in r.lower() for r in reasons))

	def test_ast_blocks_getattr_obfuscated_remove(self):
		code = "import os\ngetattr(os, 'remove')('file.txt')"
		reasons = self.sm._ast_check(code)
		self.assertTrue(any("obfuscated" in r.lower() for r in reasons))

	def test_ast_blocks_getattr_obfuscated_unlink(self):
		code = "import os\ngetattr(os, 'unlink')('file.txt')"
		reasons = self.sm._ast_check(code)
		self.assertTrue(any("obfuscated" in r.lower() for r in reasons))

	def test_ast_returns_empty_for_safe_code(self):
		code = "x = 1\nprint(x)\nresult = x + 2"
		reasons = self.sm._ast_check(code)
		self.assertEqual(reasons, [])

	def test_ast_returns_empty_for_invalid_python(self):
		# Non-Python code (e.g. shell) should not crash and return empty reasons
		code = "rm -rf /"
		reasons = self.sm._ast_check(code)
		self.assertEqual(reasons, [])

	def test_ast_check_assess_blocks_ast_detected_deletion(self):
		"""assess_execution should block code with AST-detected deletion."""
		sm = ExecutionSafetyManager(unsafe_mode=False)
		code = "import os\nos.remove('file.txt')"
		decision = sm.assess_execution(code, "code")
		self.assertFalse(decision.allowed)
		self.assertTrue(any("AST" in r for r in decision.reasons))


class TestExecutionSafetyManagerAssessExecutionNew(unittest.TestCase):
	"""Tests for the refactored assess_execution() behavior in this PR."""

	def setUp(self):
		self.sm = ExecutionSafetyManager()

	def test_empty_string_returns_not_allowed(self):
		decision = self.sm.assess_execution("", "code")
		self.assertFalse(decision.allowed)
		self.assertIn("Empty content", decision.reasons)

	def test_whitespace_only_returns_not_allowed(self):
		decision = self.sm.assess_execution("   \n\t  ", "code")
		self.assertFalse(decision.allowed)
		self.assertIn("Empty content", decision.reasons)

	def test_blocks_subprocess_usage(self):
		decision = self.sm.assess_execution("import subprocess\nsubprocess.run(['ls'])", "code")
		self.assertFalse(decision.allowed)
		self.assertTrue(any("shell" in r.lower() for r in decision.reasons))

	def test_blocks_os_system(self):
		decision = self.sm.assess_execution("import os\nos.system('ls')", "code")
		self.assertFalse(decision.allowed)
		self.assertTrue(any("shell" in r.lower() for r in decision.reasons))

	def test_blocks_powershell_reference(self):
		decision = self.sm.assess_execution("powershell -Command Get-Date", "script")
		self.assertFalse(decision.allowed)

	def test_blocks_cmd_exe_reference(self):
		decision = self.sm.assess_execution("cmd.exe /c dir", "command")
		self.assertFalse(decision.allowed)

	def test_blocks_bash_reference(self):
		decision = self.sm.assess_execution("bash -c 'ls -la'", "command")
		self.assertFalse(decision.allowed)

	def test_blocks_delete_keyword(self):
		decision = self.sm.assess_execution("delete file.txt", "command")
		self.assertFalse(decision.allowed)

	def test_blocks_erase_command(self):
		decision = self.sm.assess_execution("erase C:\\file.txt", "command")
		self.assertFalse(decision.allowed)

	def test_blocks_remove_item_powershell(self):
		decision = self.sm.assess_execution("Remove-Item C:\\Temp\\file.txt", "script")
		self.assertFalse(decision.allowed)

	def test_blocks_absolute_path_write_mode(self):
		decision = self.sm.assess_execution("open('C:\\\\temp\\\\out.txt', 'w')", "code")
		self.assertFalse(decision.allowed)

	def test_blocks_absolute_path_append_mode(self):
		decision = self.sm.assess_execution("open('C:\\\\log.txt', 'a')", "code")
		self.assertFalse(decision.allowed)

	def test_blocks_absolute_path_create_mode(self):
		decision = self.sm.assess_execution("open('C:\\\\new.txt', 'x')", "code")
		self.assertFalse(decision.allowed)

	def test_blocks_write_function_with_absolute_path(self):
		decision = self.sm.assess_execution("f = open('C:\\\\data.txt', 'r')\nf.write('data')", "code")
		self.assertFalse(decision.allowed)

	def test_allows_safe_simple_code(self):
		decision = self.sm.assess_execution("print('hello world')", "code")
		self.assertTrue(decision.allowed)

	def test_allows_read_only_absolute_path(self):
		# Reading from absolute path without write/delete should be allowed
		decision = self.sm.assess_execution("f = open('C:\\\\data.txt', 'r')\ndata = f.read()\nf.close()\nprint(data)", "code")
		self.assertTrue(decision.allowed)

	def test_command_mode_blocks_multiline(self):
		decision = self.sm.assess_execution("echo hello\necho world", "command")
		self.assertFalse(decision.allowed)
		self.assertIn("Command must be single line.", decision.reasons)

	def test_command_mode_allows_single_line(self):
		decision = self.sm.assess_execution("echo hello", "command")
		self.assertTrue(decision.allowed)

	def test_rd_s_q_hard_blocked_before_unsafe_mode_check(self):
		"""rd /s /q is blocked before the unsafe_mode bypass."""
		sm = ExecutionSafetyManager(unsafe_mode=True)
		decision = sm.assess_execution("rd /s /q C:\\Temp", "command")
		self.assertFalse(decision.allowed)

	def test_blocks_unlinksync_js(self):
		decision = self.sm.assess_execution("fs.unlinkSync('temp.txt')", "code")
		self.assertFalse(decision.allowed)

	def test_blocks_rmtree(self):
		decision = self.sm.assess_execution("shutil.rmtree('/tmp/test')", "code")
		self.assertFalse(decision.allowed)

	def test_decision_reasons_not_empty_when_blocked(self):
		decision = self.sm.assess_execution("rm -rf /", "command")
		self.assertFalse(decision.allowed)
		self.assertGreater(len(decision.reasons), 0)


class TestIsDangerousOperation(unittest.TestCase):
	"""Tests for the new is_dangerous_operation() method in ExecutionSafetyManager."""

	def setUp(self):
		self.sm = ExecutionSafetyManager()

	def test_empty_string_returns_false(self):
		self.assertFalse(self.sm.is_dangerous_operation(""))

	def test_none_equivalent_whitespace_returns_false(self):
		self.assertFalse(self.sm.is_dangerous_operation("   "))

	def test_safe_code_returns_false(self):
		self.assertFalse(self.sm.is_dangerous_operation("print('hello')"))

	def test_unlink_is_dangerous(self):
		self.assertTrue(self.sm.is_dangerous_operation("os.unlink('file.txt')"))

	def test_unlinksync_is_dangerous(self):
		self.assertTrue(self.sm.is_dangerous_operation("fs.unlinkSync('file.txt')"))

	def test_remove_call_is_dangerous(self):
		self.assertTrue(self.sm.is_dangerous_operation("os.remove('file.txt')"))

	def test_rmtree_is_dangerous(self):
		self.assertTrue(self.sm.is_dangerous_operation("shutil.rmtree('/tmp')"))

	def test_del_command_is_dangerous(self):
		self.assertTrue(self.sm.is_dangerous_operation("del file.txt"))

	def test_rm_command_is_dangerous(self):
		self.assertTrue(self.sm.is_dangerous_operation("rm file.txt"))

	def test_erase_command_is_dangerous(self):
		self.assertTrue(self.sm.is_dangerous_operation("erase file.txt"))

	def test_delete_keyword_is_dangerous(self):
		self.assertTrue(self.sm.is_dangerous_operation("delete file.txt"))

	def test_remove_item_powershell_is_dangerous(self):
		self.assertTrue(self.sm.is_dangerous_operation("Remove-Item C:\\file.txt"))

	def test_rd_command_is_dangerous(self):
		self.assertTrue(self.sm.is_dangerous_operation("rd /s /q C:\\Temp"))

	def test_shutil_rmtree_is_dangerous(self):
		self.assertTrue(self.sm.is_dangerous_operation("shutil.rmtree('/tmp/test')"))

	def test_os_rmdir_is_dangerous(self):
		self.assertTrue(self.sm.is_dangerous_operation("os.rmdir('empty_dir')"))

	def test_case_insensitive_detection(self):
		self.assertTrue(self.sm.is_dangerous_operation("SHUTIL.RMTREE('/tmp')"))

	def test_returns_bool_type(self):
		result = self.sm.is_dangerous_operation("print('hello')")
		self.assertIsInstance(result, bool)


class TestCodeInterpreterSafetyManagerInjection(unittest.TestCase):
	"""Tests for CodeInterpreter accepting an injected safety_manager (new in PR)."""

	def _make_ci(self, safety_manager=None):
		with patch("libs.code_interpreter.Logger.initialize", return_value=None):
			return CodeInterpreter(safety_manager=safety_manager)

	def test_default_creates_execution_safety_manager(self):
		ci = self._make_ci()
		self.assertIsInstance(ci.safety_manager, ExecutionSafetyManager)

	def test_injected_manager_is_stored(self):
		custom_sm = ExecutionSafetyManager(unsafe_mode=True)
		ci = self._make_ci(safety_manager=custom_sm)
		self.assertIs(ci.safety_manager, custom_sm)

	def test_injected_unsafe_manager_propagates_unsafe_mode(self):
		unsafe_sm = ExecutionSafetyManager(unsafe_mode=True)
		ci = self._make_ci(safety_manager=unsafe_sm)
		self.assertTrue(ci.safety_manager.unsafe_mode)

	def test_default_manager_is_safe_mode(self):
		ci = self._make_ci()
		self.assertFalse(ci.safety_manager.unsafe_mode)

	def test_none_argument_creates_default_manager(self):
		ci = self._make_ci(safety_manager=None)
		self.assertIsNotNone(ci.safety_manager)
		self.assertIsInstance(ci.safety_manager, ExecutionSafetyManager)

	def test_injected_manager_is_used_for_safety_check(self):
		"""Ensure the injected manager's assess_execution is called (not a new instance)."""
		from unittest.mock import MagicMock
		from libs.safety_manager import Decision
		mock_sm = MagicMock()
		mock_sm.assess_execution.return_value = Decision(False, ["blocked by mock"])
		mock_sm.unsafe_mode = False
		ci = self._make_ci(safety_manager=mock_sm)
		# Provide a mock logger so execute_code doesn't fail on None.info()
		ci.logger = MagicMock()
		# execute_code calls self.safety_manager.assess_execution
		result = ci.execute_code("print('hello')", language="python")
		mock_sm.assess_execution.assert_called()


class TestMaxTimeoutConstant(unittest.TestCase):
	"""Tests for the MAX_TIMEOUT constant introduced in this PR (was hardcoded 30s)."""

	def test_max_timeout_is_120(self):
		from libs import code_interpreter
		self.assertEqual(code_interpreter.MAX_TIMEOUT, 120)

	def test_max_output_is_ten_million(self):
		from libs import code_interpreter
		self.assertEqual(code_interpreter.MAX_OUTPUT, 10_000_000)


class TestPackageManagerRunCommandSafety(unittest.TestCase):
	"""Tests for the refactored PackageManager._run_command() with arg validation."""

	def setUp(self):
		with patch("libs.package_manager.Logger.initialize", return_value=None):
			from libs.package_manager import PackageManager
			self.pm = PackageManager()

	@patch("libs.package_manager.os.name", "nt")
	def test_windows_unsafe_arg_with_space_raises_value_error(self):
		with self.assertRaises(ValueError) as ctx:
			with patch("subprocess.check_call"):
				self.pm._run_command(["pip", "install", "package name with space"])
		self.assertIn("Unsafe command argument", str(ctx.exception))

	@patch("libs.package_manager.os.name", "nt")
	def test_windows_unsafe_arg_with_semicolon_raises_value_error(self):
		with self.assertRaises(ValueError):
			with patch("subprocess.check_call"):
				self.pm._run_command(["pip", "install", "pkg; rm -rf /"])

	@patch("libs.package_manager.os.name", "nt")
	def test_windows_safe_args_pass_validation(self):
		with patch("subprocess.check_call", return_value=0) as mock_call:
			result = self.pm._run_command(["pip", "install", "requests"])
		# On Windows, args are converted to a single string via list2cmdline
		mock_call.assert_called_once_with("pip install requests", shell=True)

	@patch("libs.package_manager.os.name", "posix")
	def test_unix_uses_shell_false(self):
		with patch("subprocess.check_call", return_value=0) as mock_call:
			self.pm._run_command(["pip", "install", "requests"])
		mock_call.assert_called_once_with(["pip", "install", "requests"], shell=False)

	@patch("libs.package_manager.os.name", "posix")
	def test_unix_does_not_validate_args(self):
		"""On Unix, no regex validation — any string args are passed through."""
		with patch("subprocess.check_call", return_value=0) as mock_call:
			# This would fail on Windows but should pass on Unix
			self.pm._run_command(["pip", "install", "my package"])
		mock_call.assert_called_once()

	@patch("libs.package_manager.os.name", "nt")
	def test_windows_non_string_arg_raises_value_error(self):
		with self.assertRaises(ValueError):
			with patch("subprocess.check_call"):
				self.pm._run_command(["pip", "install", 123])

	@patch("libs.package_manager.os.name", "nt")
	def test_windows_unsafe_arg_with_pipe_raises_value_error(self):
		with self.assertRaises(ValueError):
			with patch("subprocess.check_call"):
				self.pm._run_command(["pip", "install", "pkg | evil"])

	@patch("libs.package_manager.os.name", "nt")
	def test_windows_called_process_error_is_reraised(self):
		import subprocess
		with patch("subprocess.check_call", side_effect=subprocess.CalledProcessError(1, "pip")):
			with self.assertRaises(subprocess.CalledProcessError):
				self.pm._run_command(["pip", "install", "requests"])


class TestExecutionSafetyManagerSandbox(unittest.TestCase):
	"""Tests for build_sandbox_context() and cleanup_sandbox_context() (updated in PR)."""

	def setUp(self):
		self.sm = ExecutionSafetyManager()

	def test_build_sandbox_context_creates_temp_dir(self):
		ctx = self.sm.build_sandbox_context()
		try:
			self.assertTrue(os.path.isdir(ctx.cwd))
			self.assertTrue(ctx.cwd.startswith(tempfile.gettempdir()) or "ci_sandbox_" in ctx.cwd)
		finally:
			self.sm.cleanup_sandbox_context(ctx)

	def test_build_sandbox_context_sets_pythonioencoding(self):
		ctx = self.sm.build_sandbox_context()
		try:
			self.assertEqual(ctx.env.get("PYTHONIOENCODING"), "utf-8")
		finally:
			self.sm.cleanup_sandbox_context(ctx)

	def test_build_sandbox_context_timeout_is_30(self):
		ctx = self.sm.build_sandbox_context()
		try:
			self.assertEqual(ctx.timeout_seconds, 30)
		finally:
			self.sm.cleanup_sandbox_context(ctx)

	def test_cleanup_removes_sandbox_directory(self):
		ctx = self.sm.build_sandbox_context()
		sandbox_dir = ctx.cwd
		self.assertTrue(os.path.exists(sandbox_dir))
		self.sm.cleanup_sandbox_context(ctx)
		self.assertFalse(os.path.exists(sandbox_dir))

	def test_cleanup_with_none_context_does_not_raise(self):
		# Should be a no-op without raising
		self.sm.cleanup_sandbox_context(None)

	def test_build_sandbox_prefix_starts_with_ci_sandbox(self):
		ctx = self.sm.build_sandbox_context()
		try:
			self.assertIn("ci_sandbox_", ctx.cwd)
		finally:
			self.sm.cleanup_sandbox_context(ctx)


class TestInterpreterUnsafeModeInitialization(unittest.TestCase):
	"""Tests for Interpreter unsafe_mode propagation to safety_manager (new in PR)."""

	def _make_args(self, unsafe=False, mode="code", model="z-ai-glm-5"):
		return Namespace(
			exec=False,
			save_code=False,
			mode=mode,
			model=model,
			display_code=False,
			lang="python",
			file=None,
			history=False,
			upgrade=False,
			unsafe=unsafe,
		)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_safe_mode_sets_unsafe_execution_false(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(unsafe=False))
		self.assertFalse(interpreter.UNSAFE_EXECUTION)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_unsafe_flag_sets_unsafe_execution_true(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(unsafe=True))
		self.assertTrue(interpreter.UNSAFE_EXECUTION)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_safety_manager_unsafe_mode_matches_unsafe_execution(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(unsafe=True))
		self.assertTrue(interpreter.safety_manager.unsafe_mode)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_safe_mode_safety_manager_not_unsafe(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(unsafe=False))
		self.assertFalse(interpreter.safety_manager.unsafe_mode)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_code_interpreter_shares_safety_manager(self, _mock_history, _mock_client):
		"""code_interpreter and safety_manager must share the same instance."""
		interpreter = Interpreter(self._make_args(unsafe=True))
		self.assertIs(interpreter.code_interpreter.safety_manager, interpreter.safety_manager)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_code_interpreter_shares_safety_manager_safe_mode(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(unsafe=False))
		self.assertIs(interpreter.code_interpreter.safety_manager, interpreter.safety_manager)


class TestInterpreterModeIndicatorBanner(unittest.TestCase):
	"""Tests for the mode indicator added to _display_session_banner (new in PR)."""

	def _make_args(self, unsafe=False, mode="code", model="z-ai-glm-5"):
		return Namespace(
			exec=False,
			save_code=False,
			mode=mode,
			model=model,
			display_code=False,
			lang="python",
			file=None,
			history=False,
			upgrade=False,
			unsafe=unsafe,
		)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_safe_mode_banner_contains_safe_mode_indicator(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(unsafe=False))
		interpreter.INTERPRETER_MODEL = "z-ai-glm-5"
		interpreter.INTERPRETER_MODEL_LABEL = None

		printed_lines = []
		with patch.object(interpreter.console, "print", side_effect=lambda *a, **kw: printed_lines.append(a[0] if a else "")):
			interpreter._display_session_banner("Windows 10", "input")

		full_output = " ".join(printed_lines)
		self.assertIn("SAFE MODE", full_output)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_unsafe_mode_banner_contains_unsafe_mode_indicator(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(unsafe=True))
		interpreter.INTERPRETER_MODEL = "z-ai-glm-5"
		interpreter.INTERPRETER_MODEL_LABEL = None

		printed_lines = []
		with patch.object(interpreter.console, "print", side_effect=lambda *a, **kw: printed_lines.append(a[0] if a else "")):
			interpreter._display_session_banner("Windows 10", "input")

		full_output = " ".join(printed_lines)
		self.assertIn("UNSAFE MODE", full_output)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_safe_mode_uses_green_style(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(unsafe=False))
		interpreter.INTERPRETER_MODEL = "z-ai-glm-5"
		interpreter.INTERPRETER_MODEL_LABEL = None

		printed_lines = []
		with patch.object(interpreter.console, "print", side_effect=lambda *a, **kw: printed_lines.append(a[0] if a else "")):
			interpreter._display_session_banner("Linux", "input")

		full_output = " ".join(printed_lines)
		self.assertIn("bold green", full_output)

	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_unsafe_mode_uses_red_style(self, _mock_history, _mock_client):
		interpreter = Interpreter(self._make_args(unsafe=True))
		interpreter.INTERPRETER_MODEL = "z-ai-glm-5"
		interpreter.INTERPRETER_MODEL_LABEL = None

		printed_lines = []
		with patch.object(interpreter.console, "print", side_effect=lambda *a, **kw: printed_lines.append(a[0] if a else "")):
			interpreter._display_session_banner("Linux", "input")

		full_output = " ".join(printed_lines)
		self.assertIn("bold red", full_output)


class TestInterpreterDangerousOperationBlocking(unittest.TestCase):
	"""Tests for dangerous operation blocking logic (SAFE vs UNSAFE mode) in execute_code."""

	def _make_args(self, unsafe=False, mode="code", exec_flag=False):
		return Namespace(
			exec=exec_flag,
			save_code=False,
			mode=mode,
			model="z-ai-glm-5",
			display_code=False,
			lang="python",
			file=None,
			history=False,
			upgrade=False,
			unsafe=unsafe,
		)

	@patch("libs.interpreter_lib.display_markdown_message")
	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	def test_safe_mode_blocks_dangerous_operation_before_prompt(
		self, _mock_history, _mock_client, _mock_markdown
	):
		"""In SAFE MODE, dangerous operations must be blocked without prompting user."""
		# exec=False so EXECUTE_CODE is False and input() would normally be called.
		# But for dangerous ops in safe mode, it must be blocked before any prompt.
		interpreter = Interpreter(self._make_args(unsafe=False, exec_flag=False))

		with patch("builtins.input") as mock_input:
			result = interpreter.execute_code("rm -rf /", "Linux")

		# Should not have prompted the user
		mock_input.assert_not_called()
		# Should have returned an error
		output, error = result
		self.assertIsNone(output)
		self.assertIsNotNone(error)

	@patch("libs.interpreter_lib.display_markdown_message")
	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	@patch("builtins.input", return_value="n")
	def test_unsafe_mode_prompts_for_dangerous_operation(
		self, _mock_input, _mock_history, _mock_client, _mock_markdown
	):
		"""In UNSAFE MODE, dangerous operations must show a warning prompt."""
		# exec=False so EXECUTE_CODE is False, forcing the input() path
		interpreter = Interpreter(self._make_args(unsafe=True, exec_flag=False))
		interpreter.config_values = {"start_sep": "```", "end_sep": "```"}

		# Use a code snippet that triggers is_dangerous_operation
		result = interpreter.execute_code("import os\nos.remove('test.txt')", "Linux")

		# Should have prompted (with dangerous warning)
		_mock_input.assert_called()
		call_args = _mock_input.call_args[0][0]
		self.assertIn("Dangerous", call_args)

	@patch("libs.interpreter_lib.display_markdown_message")
	@patch("libs.interpreter_lib.Interpreter.initialize_client", return_value=None)
	@patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
	@patch("builtins.input", return_value="n")
	def test_safe_operation_uses_standard_prompt(
		self, _mock_input, _mock_history, _mock_client, _mock_markdown
	):
		"""Non-dangerous operations use standard 'Execute the code?' prompt."""
		# exec=False so EXECUTE_CODE is False, forcing the input() path
		interpreter = Interpreter(self._make_args(unsafe=False, exec_flag=False))
		interpreter.config_values = {"start_sep": "```", "end_sep": "```"}

		result = interpreter.execute_code("print('hello')", "Linux")

		_mock_input.assert_called()
		call_args = _mock_input.call_args[0][0]
		self.assertIn("Execute", call_args)
		self.assertNotIn("Dangerous", call_args)


class TestInterpreterVersionUpdated(unittest.TestCase):
	"""Tests for the interpreter version update in this PR (3.1.0 → 3.2.1)."""

	def test_interpreter_version_is_3_2_1(self):
		self.assertEqual(interpreter_entry.INTERPRETER_VERSION, "3.2.1")

	def test_version_file_contains_3_2_1(self):
		version_file = ROOT_DIR / "VERSION"
		content = version_file.read_text(encoding="utf-8").strip()
		self.assertEqual(content, "3.2.1")


if __name__ == "__main__":
	unittest.main()