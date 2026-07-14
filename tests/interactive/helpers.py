"""Shared mock interpreter factory for interactive main_loop tests (#226)."""

from __future__ import annotations

from unittest.mock import MagicMock


def make_interp(**overrides):
	"""Fully wired MagicMock interpreter ready for ``run_interpreter_main``."""
	interp = MagicMock()
	interp.args = MagicMock(
		file=None,
		science=False,
		interactive_charts=False,
		plot_theme=None,
		no_auto_install=True,
		output_format=None,
		yolo=False,
		yes=False,
		search=False,
		search_provider=None,
		search_api_key=None,
	)
	interp.interpreter_version = "3.4.0"
	interp.INTERPRETER_PROMPT_FILE = False
	interp.INTERPRETER_PROMPT_INPUT = True
	interp.AUTO_YES = False
	interp.AGENT_MODE = False
	interp.SCRIPT_MODE = False
	interp.COMMAND_MODE = False
	interp.VISION_MODE = False
	interp.CHAT_MODE = False
	interp.CODE_MODE = True
	interp.INTERPRETER_MODE = "code"
	interp.INTERPRETER_LANGUAGE = "python"
	interp.INTERPRETER_MODEL = "gpt-4o"
	interp.INTERPRETER_MODEL_LABEL = "gpt-4o"
	interp.UNSAFE_EXECUTION = False
	interp.DISPLAY_CODE = False
	interp.SAVE_CODE = False
	interp.EXECUTE_CODE = True
	interp.INTERPRETER_HISTORY = False
	interp.config_values = {"start_sep": "```", "end_sep": "```"}
	interp.logger = MagicMock()
	interp.console = MagicMock()
	interp.terminal_ui = None
	interp.utility_manager = MagicMock()
	interp.utility_manager.get_os_platform.return_value = ("Windows", "10", "x64")
	# extract_file_name must default to None (no file in prompt): a bare
	# MagicMock return value here is not None, so it's not-None-checked into
	# main_loop's file-attachment branch, where the mocked full_path is
	# treated as an int fd via MagicMock's default __index__ (returns 1) by
	# os.path.isfile/open — silently operating on fd 1 (stdout) and closing
	# it, corrupting the process's stdout handle.
	interp.utility_manager.extract_file_name.return_value = None
	def _read_file(path):
		with open(path, encoding="utf-8") as fh:
			return fh.read()

	interp.utility_manager.read_file.side_effect = _read_file
	interp.history_manager = MagicMock()
	interp.package_manager = MagicMock()
	interp.package_manager.get_system_modules.return_value = []
	interp.memory = MagicMock()
	interp.memory.stats.return_value = {
		"entry_count": 5,
		"total_tokens": 1200,
		"max_tokens": 8000,
		"history_file": "history/history.json",
	}
	interp.memory.get_context.return_value = []
	interp.tool_registry = MagicMock()
	interp.tool_registry.list_tools.return_value = [
		{"name": "read_file", "description": "Read a file"},
		{"name": "write_file", "description": "Write a file"},
	]
	interp.tool_registry.get.return_value = None
	interp.code_interpreter = MagicMock()
	interp.code_interpreter.extract_code.side_effect = (
		lambda text, *a, **k: "print('hello from test')" if text and "```" in str(text) else text
	)
	interp.safety_manager = MagicMock()
	interp.history = []
	interp.conversation_history = []
	interp.session_store = None
	interp.data_session = None
	interp._attached_files = []
	interp._pending_images = []
	interp._last_execution_approved = True
	interp._last_response_was_streamed = False
	interp._structured_output_active.return_value = False
	interp._display_session_banner = MagicMock()
	interp._is_recoverable_runtime_error.return_value = False
	interp._maybe_simplify_generated_code.side_effect = lambda task, code: code
	interp.get_mode_prompt.side_effect = lambda task, os_name: f"Task: {task}"
	interp._generate_content_with_retries = MagicMock(return_value="ok")
	interp._execute_generated_output = MagicMock(return_value=("ok", None, None))
	interp.emit_turn_result = MagicMock()
	interp.record_session_turn = MagicMock()
	interp.handle_session_command = MagicMock(return_value=True)
	interp.__dict__.update(overrides)
	return interp
