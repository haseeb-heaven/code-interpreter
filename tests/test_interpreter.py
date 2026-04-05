import os
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


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIGS_DIR = ROOT_DIR / "configs"


def _read_hf_model(config_path: Path) -> str:
    for line in config_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped.startswith("HF_MODEL") and "=" in stripped:
            return stripped.split("=", 1)[1].strip().strip("'").strip('"')
    raise AssertionError(f"HF_MODEL missing in config: {config_path}")



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
    @patch("libs.utility_manager.UtilityManager.read_config_file", return_value={"HF_MODEL": "gpt-4o"})
    def test_initialize_client_loads_env_from_repo_root(
        self, _mock_read_config, load_dotenv_mock, _mock_getenv, _mock_history
    ):
        Interpreter(self._make_args(model="gpt-4o"))
        expected_env_path = os.path.join(os.getcwd(), ".env")
        load_dotenv_mock.assert_any_call(dotenv_path=expected_env_path, override=True)

    @patch("libs.utility_manager.UtilityManager.initialize_readline_history", return_value=None)
    @patch("libs.interpreter_lib.os.getenv", side_effect=lambda key: "gsk-test-123" if key == "GROQ_API_KEY" else None)
    @patch("libs.interpreter_lib.load_dotenv")
    @patch("libs.utility_manager.UtilityManager.read_config_file", return_value={"HF_MODEL": "groq/openai/gpt-oss-20b"})
    def test_initialize_client_uses_shared_default_model_when_missing(
        self, _mock_read_config, _mock_load_dotenv, _mock_getenv, _mock_history
    ):
        with patch("libs.utility_manager.UtilityManager.get_default_model_name", return_value="groq-gpt-oss-20b"):
            interpreter = Interpreter(self._make_args(model=None))

        self.assertEqual(interpreter.INTERPRETER_MODEL, "groq/openai/gpt-oss-20b")
        self.assertEqual(interpreter.INTERPRETER_MODEL_LABEL, "groq-gpt-oss-20b")

    def test_every_config_is_parseable_and_has_hf_model(self):
        utility_manager = UtilityManager()
        config_files = sorted(CONFIGS_DIR.glob("*.config"))
        self.assertTrue(config_files, "No config files found")

        for config_file in config_files:
            with self.subTest(config=config_file.name):
                values = utility_manager.read_config_file(str(config_file))
                self.assertIn("HF_MODEL", values)
                self.assertTrue(values["HF_MODEL"].strip())

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
            skip_first_line=True,
            code_mode=True,
        )
        self.assertEqual(extracted, "print('OK')")

    def test_legacy_alias_configs_are_mapped_to_modern_targets(self):
        expected_aliases = {
            "gpt-3.5-turbo.config": "gpt-4o-mini",
            "gpt-4.config": "gpt-4",
            "gpt-o1-mini.config": "o1",
            "gpt-o1-preview.config": "o1-preview",
            "gemini-pro.config": "gemini/gemini-2.5-pro",
            "gemini-1.5-pro.config": "gemini/gemini-2.5-pro",
            "gemini-1.5-flash.config": "gemini/gemini-2.5-flash",
            "claude-2.config": "claude-2",
            "claude-2.1.config": "claude-2.1",
            "claude-3-7-sonnet.config": "claude-3-7-sonnet",
            "deepseek-coder.config": "deepseek-chat",
            "groq-mixtral.config": "groq/llama-3.3-70b-versatile",
            "groq-llama2.config": "groq/llama-3.1-8b-instant",
        }
        for config_name, expected_hf_model in expected_aliases.items():
            with self.subTest(config=config_name):
                hf_model = _read_hf_model(CONFIGS_DIR / config_name)
                self.assertEqual(hf_model, expected_hf_model)

    def test_new_provider_configs_exist(self):
        required_configs = {
            "openrouter-free.config": "openrouter/free",
            "nvidia-nemotron.config": "nvidia/nemotron-3-super-120b-a12b",
            "z-ai-glm-5.config": "glm-5",
            "browser-use-bu-max.config": "bu-max",
            "openrouter-qwen3-coder.config": "qwen/qwen3-coder:free",
            "openrouter-claude-opus-4-6.config": "anthropic/claude-opus-4.6",
            "openrouter-mimo-v2-pro.config": "xiaomi/mimo-v2-pro",
            "openrouter-gpt-5-4.config": "openai/gpt-5.4",
            "openrouter-deepseek-v3-2.config": "deepseek/deepseek-v3.2",
            "openrouter-qwen3-coder-480b-free.config": "qwen/qwen3-coder-480b:free",
            "openrouter-mimo-v2-flash-free.config": "xiaomi/mimo-v2-flash:free",
            "openrouter-nemotron-3-super-free.config": "nvidia/nemotron-3-super:free",
            "openrouter-minimax-m2-5-free.config": "minimax/minimax-m2.5:free",
            "openrouter-qwen3-6-plus-free.config": "qwen/qwen3.6-plus:free",
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
        config_files = sorted(CONFIGS_DIR.glob("*.config"))

        for config_file in config_files:
            if config_file.name == "local-model.config":
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
                    with patch.object(
                        interpreter,
                        "_run_openai_compatible_completion",
                        return_value={"choices": [{"message": {"content": "ok"}}]},
                    ) as compatible_mock, patch.object(interpreter.utility_manager, "_extract_content", return_value="ok"):
                        response = interpreter.generate_content(
                            message="healthcheck",
                            chat_history=[],
                            config_values=model_config_values,
                        )
                    self.assertEqual(response, "ok")
                    compatible_mock.assert_called_once()
                    self.assertEqual(interpreter.INTERPRETER_MODEL, expected_model)
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
        interpreter.config_values = {"start_sep": "```", "end_sep": "```", "skip_first_line": "False"}

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
        interpreter.config_values = {"start_sep": "```", "end_sep": "```", "skip_first_line": "False"}

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
        interpreter.config_values = {"start_sep": "```", "end_sep": "```", "skip_first_line": "False"}

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


class TestBuildParser(unittest.TestCase):
    """Tests for the build_parser() function added in this PR."""

    def test_interpreter_version_is_3_1_0(self):
        self.assertEqual(interpreter_entry.INTERPRETER_VERSION, "3.1.0")

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
        self.assertEqual(kwargs["env"], custom_env)

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
        self.assertEqual(result[0], "/bin/bash")
        self.assertIn("--noprofile", result)
        self.assertIn("--norc", result)
        self.assertEqual(result[-1], "echo hello")

    @patch("libs.code_interpreter.os.name", "posix")
    @patch("libs.code_interpreter.os.path.exists", return_value=False)
    def test_unix_without_bash_falls_back_to_sh(self, _mock_exists):
        result = self.ci._build_command_invocation("echo hello")
        self.assertEqual(result[0], "sh")
        self.assertIn("-c", result)
        self.assertEqual(result[-1], "echo hello")

    @patch("libs.code_interpreter.os.name", "nt")
    def test_windows_uses_cmd_exe(self):
        result = self.ci._build_command_invocation("dir")
        self.assertEqual(result[0], "cmd.exe")
        self.assertIn("/c", result)
        self.assertEqual(result[-1], "dir")

    @patch("libs.code_interpreter.os.name", "posix")
    @patch("libs.code_interpreter.os.path.exists", return_value=True)
    def test_command_is_last_element(self, _mock_exists):
        cmd = "ls -la /tmp"
        result = self.ci._build_command_invocation(cmd)
        self.assertEqual(result[-1], cmd)


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
    def test_execute_script_defaults_to_30s_timeout_without_sandbox(self, mock_popen):
        mock_process = mock_popen.return_value
        mock_process.communicate.return_value = (b"hi", b"")
        mock_process.returncode = 0
        with patch("libs.code_interpreter.os.path.exists", return_value=True), \
             patch("libs.code_interpreter.os.name", "posix"):
            self.ci._execute_script("echo hi", shell="bash")
        mock_process.communicate.assert_called_once_with(timeout=30)

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
             patch("libs.code_interpreter.os.name", "posix"):
            result = self.ci._execute_script("sleep 100", shell="bash")
            self.assertIsNone(result[0])
            self.assertEqual(result[1], "Execution timed out.")
        mock_process.kill.assert_called_once()


class TestNewConfigFilesFromPR(unittest.TestCase):
    """Tests for new and modified config files introduced in this PR."""

    def _read_config(self, name):
        from libs.utility_manager import UtilityManager
        return UtilityManager().read_config_file(str(CONFIGS_DIR / name))

    def _read_hf_model(self, name):
        return _read_hf_model(CONFIGS_DIR / name)

    # --- New Claude configs ---

    def test_claude_3_7_sonnet_config_maps_to_claude_sonnet_4_6(self):
        self.assertEqual(self._read_hf_model("claude-3-7-sonnet.config"), "claude-3-7-sonnet")

    def test_claude_3_5_sonnet_config_maps_to_claude_sonnet_4_6(self):
        self.assertEqual(self._read_hf_model("claude-3-5-sonnet.config"), "claude-sonnet-4-6")

    def test_claude_sonnet_4_6_config_has_correct_model(self):
        self.assertEqual(self._read_hf_model("claude-sonnet-4-6.config"), "claude-sonnet-4-6")

    def test_claude_opus_4_6_config_has_correct_model(self):
        self.assertEqual(self._read_hf_model("claude-opus-4-6.config"), "claude-opus-4-6")

    def test_claude_haiku_4_5_config_has_correct_model(self):
        self.assertEqual(self._read_hf_model("claude-haiku-4-5.config"), "claude-haiku-4-5")

    def test_claude_3_opus_remapped_to_claude_opus_4_6(self):
        self.assertEqual(self._read_hf_model("claude-3-opus.config"), "claude-opus-4-6")

    # --- Legacy HuggingFace configs remapped ---

    def test_code_llama_maps_to_meta_llama_3(self):
        self.assertEqual(
            self._read_hf_model("code-llama.config"),
            "huggingface/meta-llama/Meta-Llama-3-8B-Instruct",
        )

    def test_code_llama_phind_maps_to_meta_llama_3(self):
        self.assertEqual(
            self._read_hf_model("code-llama-phind.config"),
            "huggingface/meta-llama/Meta-Llama-3-8B-Instruct",
        )

    # --- New Gemini configs (legacy aliases) ---

    def test_gemini_1_5_pro_maps_to_gemini_2_5_pro(self):
        self.assertEqual(self._read_hf_model("gemini-1.5-pro.config"), "gemini/gemini-2.5-pro")

    def test_gemini_1_5_flash_maps_to_gemini_2_5_flash(self):
        self.assertEqual(self._read_hf_model("gemini-1.5-flash.config"), "gemini/gemini-2.5-flash")

    # --- Separator changes: all new configs use single backtick ---

    def test_claude_sonnet_4_6_config_uses_single_backtick_separator(self):
        config = self._read_config("claude-sonnet-4-6.config")
        self.assertEqual(config.get("start_sep"), "`")
        self.assertEqual(config.get("end_sep"), "`")

    def test_gemini_1_5_pro_config_uses_single_backtick_separator(self):
        config = self._read_config("gemini-1.5-pro.config")
        self.assertEqual(config.get("start_sep"), "`")
        self.assertEqual(config.get("end_sep"), "`")

    def test_deepseek_chat_config_uses_single_backtick_separator(self):
        config = self._read_config("deepseek-chat.config")
        self.assertEqual(config.get("start_sep"), "`")
        self.assertEqual(config.get("end_sep"), "`")

    def test_deepseek_reasoner_config_uses_single_backtick_separator(self):
        config = self._read_config("deepseek-reasoner.config")
        self.assertEqual(config.get("start_sep"), "`")
        self.assertEqual(config.get("end_sep"), "`")

    # --- max_tokens updated in deepseek configs ---

    def test_deepseek_chat_config_max_tokens_is_4096(self):
        config = self._read_config("deepseek-chat.config")
        self.assertEqual(config.get("max_tokens"), "4096")

    def test_deepseek_coder_config_max_tokens_is_4096(self):
        config = self._read_config("deepseek-coder.config")
        self.assertEqual(config.get("max_tokens"), "4096")

    def test_deepseek_reasoner_config_max_tokens_is_4096(self):
        config = self._read_config("deepseek-reasoner.config")
        self.assertEqual(config.get("max_tokens"), "4096")

    # --- Browser Use config specific fields ---

    def test_browser_use_config_has_provider_field(self):
        config = self._read_config("browser-use-bu-max.config")
        self.assertEqual(config.get("provider"), "browser-use")

    def test_browser_use_config_has_correct_api_base(self):
        config = self._read_config("browser-use-bu-max.config")
        self.assertEqual(config.get("api_base"), "https://api.browser-use.com/api/v3")

    def test_browser_use_config_has_timeout_setting(self):
        config = self._read_config("browser-use-bu-max.config")
        self.assertIn("browser_use_timeout", config)

    def test_browser_use_config_has_poll_interval(self):
        config = self._read_config("browser-use-bu-max.config")
        self.assertIn("browser_use_poll_interval", config)

    def test_browser_use_config_max_tokens_is_2048(self):
        config = self._read_config("browser-use-bu-max.config")
        self.assertEqual(config.get("max_tokens"), "2048")

    # --- deepseek-coder remapped to deepseek-chat ---

    def test_deepseek_coder_config_remapped_to_deepseek_chat_model(self):
        self.assertEqual(self._read_hf_model("deepseek-coder.config"), "deepseek-chat")

    # --- skip_first_line updated in deepseek configs ---

    def test_deepseek_chat_skip_first_line_is_true(self):
        config = self._read_config("deepseek-chat.config")
        self.assertEqual(config.get("skip_first_line").strip().lower(), "true")

    def test_deepseek_coder_skip_first_line_is_true(self):
        config = self._read_config("deepseek-coder.config")
        self.assertEqual(config.get("skip_first_line").strip().lower(), "true")


class TestVersionFile(unittest.TestCase):
    """Tests for the VERSION file added in this PR."""

    def test_version_file_exists(self):
        version_file = ROOT_DIR / "VERSION"
        self.assertTrue(version_file.exists(), "VERSION file should exist")

    def test_version_file_contains_3_1_0(self):
        version_file = ROOT_DIR / "VERSION"
        content = version_file.read_text(encoding="utf-8").strip()
        self.assertEqual(content, "3.1.0")

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


if __name__ == "__main__":
    unittest.main()