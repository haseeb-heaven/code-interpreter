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
from libs.utility_manager import UtilityManager


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIGS_DIR = ROOT_DIR / "configs"


def _read_hf_model(config_path: Path) -> str:
    for line in config_path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if stripped.startswith("HF_MODEL") and "=" in stripped:
            return stripped.split("=", 1)[1].strip().strip("'").strip('"')
    raise AssertionError(f"HF_MODEL missing in config: {config_path}")


def _expected_completion_model(model_name: str) -> str:
    if model_name.startswith(("gpt", "o1", "o3", "o4")):
        return model_name

    if "gemini" in model_name:
        if model_name == "gemini-pro":
            return "gemini/gemini-2.5-pro"
        if model_name == "gemini-1.5-pro":
            return "gemini/gemini-2.5-pro"
        if model_name == "gemini-1.5-flash":
            return "gemini/gemini-2.5-flash"
        return model_name

    if "groq" in model_name:
        if "groq-llama-3.3" in model_name:
            return "groq/llama-3.3-70b-versatile"
        if "groq-llama-3.1-8b" in model_name:
            return "groq/llama-3.1-8b-instant"
        if "groq-llama2" in model_name:
            return "groq/llama-3.1-8b-instant"
        if "groq-mixtral" in model_name:
            return "groq/llama-3.3-70b-versatile"
        if "groq-gemma" in model_name:
            return "groq/openai/gpt-oss-20b"
        return model_name

    if "claude" in model_name:
        if "claude-2.1" in model_name:
            return "claude-sonnet-4-6"
        if "claude-2" in model_name:
            return "claude-sonnet-4-6"
        if "claude-3-7-sonnet" in model_name:
            return "claude-sonnet-4-6"
        if "claude-3-5-sonnet" in model_name:
            return "claude-sonnet-4-6"
        if "claude-3-5-haiku" in model_name:
            return "claude-haiku-4-5"
        if "claude-3-sonnet" in model_name:
            return "claude-sonnet-4-6"
        if "claude-3-opus" in model_name:
            return "claude-opus-4-6"
        return model_name

    if "local" in model_name:
        return model_name

    if model_name.startswith("nvidia/"):
        return model_name

    if model_name.startswith(("glm-", "z-ai/", "zai/")):
        return model_name

    if model_name.startswith(("bu-", "browser-use/")):
        return model_name

    if "deepseek" in model_name:
        if not model_name.startswith("deepseek/"):
            return "deepseek/" + model_name
        return model_name

    if "huggingface/" not in model_name:
        return "huggingface/" + model_name
    return model_name


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
            "gpt-4.config": "gpt-4.1",
            "gpt-o1-mini.config": "o1",
            "gpt-o1-preview.config": "o1",
            "gemini-pro.config": "gemini/gemini-2.5-pro",
            "gemini-1.5-pro.config": "gemini/gemini-2.5-pro",
            "gemini-1.5-flash.config": "gemini/gemini-2.5-flash",
            "claude-2.config": "claude-sonnet-4-6",
            "claude-2.1.config": "claude-sonnet-4-6",
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
            "nvidia-nemotron.config": "nvidia/nemotron-3-super-120b-a12b",
            "z-ai-glm-5.config": "glm-5",
            "browser-use-bu-max.config": "bu-max",
        }
        for config_name, expected_hf_model in required_configs.items():
            with self.subTest(config=config_name):
                hf_model = _read_hf_model(CONFIGS_DIR / config_name)
                self.assertEqual(hf_model, expected_hf_model)

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
            expected_model = _expected_completion_model(model_name)
            model_config_values = utility_manager.read_config_file(str(config_file))
            interpreter.INTERPRETER_MODEL = model_name

            with self.subTest(config=config_file.name, model=model_name):
                if model_name.startswith(("bu-", "browser-use/")):
                    with patch.object(interpreter, "_generate_browser_use_content", return_value="ok-browser-use") as browser_mock:
                        response = interpreter.generate_content(
                            message="healthcheck",
                            chat_history=[],
                            config_values=model_config_values,
                        )
                    self.assertEqual(response, "ok-browser-use")
                    browser_mock.assert_called_once()
                    continue

                if model_name.startswith("nvidia/") or model_name.startswith(("glm-", "z-ai/", "zai/")):
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


if __name__ == "__main__":
    unittest.main()
