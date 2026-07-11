"""Session configuration and runtime state helpers for the Interpreter orchestrator."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SessionConfig:
	"""Typed view of Interpreter CLI/runtime settings.

	Kept as a dataclass for the modular architecture; the live Interpreter still
	exposes the historical UPPER_CASE attributes that the test suite reads/writes.
	"""

	language: str = "python"
	mode: str = "code"
	model: str = ""
	save_code: bool = False
	execute_code: bool = False
	display_code: bool = False
	unsafe: bool = False
	history: bool = False
	history_count: int = 3
	max_context_tokens: int = 8000
	history_file: str = "history/history.json"
	prompt_file: Optional[str] = None

	@classmethod
	def from_args(cls, args: Any) -> "SessionConfig":
		"""Build a SessionConfig from an argparse Namespace (or similar)."""
		file_arg = getattr(args, "file", None)
		return cls(
			language=getattr(args, "lang", None) or "python",
			mode=getattr(args, "mode", None) or "code",
			model=getattr(args, "model", None) or "",
			save_code=bool(getattr(args, "save_code", False)),
			execute_code=bool(getattr(args, "exec", False)),
			display_code=bool(getattr(args, "display_code", False)),
			unsafe=bool(getattr(args, "unsafe", False)),
			history=bool(getattr(args, "history", False)),
			history_count=3,
			max_context_tokens=int(getattr(args, "max_context_tokens", None) or 8000),
			history_file=getattr(args, "history_file", None) or "history/history.json",
			prompt_file=file_arg if file_arg not in (None, "") else (None if file_arg is None else "prompt.txt"),
		)


def load_system_message(mode: str, logger) -> str:
	"""Return the system message for the selected interpreter mode."""
	if mode == "vision":
		return (
			"You are top tier image captioner and image analyzer. "
			"Please generate a well-written description of the image that is precise, easy to understand"
		)
	if mode == "chat":
		return (
			"You are top tier chatbot. Please generate a well-written response "
			"that is precise, easy to understand"
		)

	try:
		with open("system/system_message.txt", "r") as file:
			system_message = file.read()
			if system_message != "":
				logger.info("System message read successfully")
			return system_message
	except Exception as exception:
		logger.error(f"Error occurred while reading system_message.txt: {str(exception)}")
		raise


def apply_mode_flags(target, mode: str) -> None:
	"""Set CODE/SCRIPT/COMMAND/VISION/CHAT mode flags on ``target``."""
	modes = {
		"vision": "VISION_MODE",
		"script": "SCRIPT_MODE",
		"command": "COMMAND_MODE",
		"code": "CODE_MODE",
		"chat": "CHAT_MODE",
	}
	normalized = (mode or "code").lower()
	target.INTERPRETER_MODE = normalized
	for key, attr in modes.items():
		setattr(target, attr, normalized == key)


def initialize_mode_from_args(target, args) -> None:
	"""Mirror Interpreter.initialize_mode behavior from CLI args."""
	target.CODE_MODE = True if args.mode == "code" else False
	target.SCRIPT_MODE = True if args.mode == "script" else False
	target.COMMAND_MODE = True if args.mode == "command" else False
	target.VISION_MODE = True if args.mode == "vision" else False
	target.CHAT_MODE = True if args.mode == "chat" else False
	if not target.SCRIPT_MODE and not target.COMMAND_MODE and not target.VISION_MODE and not target.CHAT_MODE:
		target.CODE_MODE = True


def display_session_banner(console, *, unsafe: bool, os_name: str, language: str,
						   mode: str, input_prompt_mode: str, model_label: str) -> None:
	"""Print the SAFE/UNSAFE session banner line."""
	short_lang = "python" if language == "python" else "javascript"
	short_prompt_mode = "input" if input_prompt_mode.lower() == "input" else "file"
	short_os_name = os_name.replace("Windows ", "Win")

	mode_indicator = "[UNSAFE MODE ⚠️]" if unsafe else "[SAFE MODE]"
	mode_style = "bold red" if unsafe else "bold green"

	session_line = (
		f"{mode_indicator} | "
		f"OS={short_os_name} | Lang={short_lang} | "
		f"Mode={mode} | Src={short_prompt_mode} | "
		f"Model={model_label}"
	)
	console.print(f"[{mode_style}]{session_line}[/{mode_style}]", overflow="ignore", no_wrap=True)


def resolve_prompt_input_flags(args) -> tuple[bool, bool]:
	"""Return (prompt_file_mode, prompt_input_mode) based on ``args.file``."""
	if args.file is None:
		return False, True
	if args.file == "":
		args.file = "prompt.txt"
	return True, False


def open_tui_settings(interp, setting_type):
	"""Open a TerminalUI selector and return the chosen settings dict."""
	if not interp.terminal_ui:
		return None
	if setting_type == "mode":
		return {"mode": interp.terminal_ui.select_mode(interp.INTERPRETER_MODE)}
	if setting_type == "model":
		return {"model": interp.terminal_ui.select_model(interp.INTERPRETER_MODEL_LABEL or interp.INTERPRETER_MODEL)}
	if setting_type == "language":
		return {"language": interp.terminal_ui.select_language(interp.INTERPRETER_LANGUAGE)}
	if setting_type == "settings":
		return interp.terminal_ui.interactive_settings(interp)
	return None


def apply_runtime_settings(interp, settings, *, display_fn, path_isfile):
	"""Apply interactive TUI/CLI runtime setting changes onto ``interp``."""
	if not settings:
		return
	if "mode" in settings and settings["mode"]:
		interp._apply_mode(settings["mode"])
	if "language" in settings and settings["language"]:
		interp.INTERPRETER_LANGUAGE = settings["language"]
	if "display_code" in settings:
		interp.DISPLAY_CODE = settings["display_code"]
	if "execute_code" in settings:
		interp.EXECUTE_CODE = settings["execute_code"]
	if "save_code" in settings:
		interp.SAVE_CODE = settings["save_code"]
	if "history" in settings:
		interp.INTERPRETER_HISTORY = settings["history"]
	if "model" in settings and settings["model"]:
		model = settings["model"]
		model_config_file = f"configs/{model}.json"
		if not path_isfile(model_config_file):
			display_fn(f"Model {model} does not exists. Please check the model name using '/list' command.")
		else:
			interp.INTERPRETER_MODEL = model
			interp.INTERPRETER_MODEL_LABEL = model
			interp.initialize_client()


def bootstrap_interpreter(interp) -> None:
	"""Apply CLI args, load system message, init client/mode/readline."""
	args = interp.args
	interp.INTERPRETER_LANGUAGE = args.lang if args.lang else "python"
	interp.SAVE_CODE = args.save_code
	interp.EXECUTE_CODE = args.exec
	interp.DISPLAY_CODE = args.display_code
	interp.INTERPRETER_MODEL = args.model if args.model else None
	interp.INTERPRETER_MODEL_LABEL = args.model if args.model else None
	interp.logger.info(f"Interpreter args model selected is '{args.model}")
	interp.logger.info(f"Interpreter model selected is '{interp.INTERPRETER_MODEL}'")
	interp.INTERPRETER_MODE = args.mode if args.mode else "code"
	interp.INTERPRETER_PROMPT_FILE, interp.INTERPRETER_PROMPT_INPUT = resolve_prompt_input_flags(args)
	interp.INTERPRETER_HISTORY = args.history if hasattr(args, "history") else False
	interp.AGENT_MODE = bool(getattr(args, "agent", False))
	interp.AUTO_YES = bool(getattr(args, "yes", False))
	interp.system_message = load_system_message(interp.INTERPRETER_MODE, interp.logger)
	interp.initialize_client()
	interp.initialize_mode()
	try:
		interp.utility_manager.initialize_readline_history()
	except Exception:
		interp.logger.error("Exception on initializing readline history")


def wire_components(interp) -> None:
	"""Attach modular collaborators onto a freshly constructed Interpreter."""
	from libs.core.model_router import ModelRouter
	from libs.core.prompt_builder import PromptBuilder
	from libs.execution.executor import CodeExecutor
	from libs.execution.repairer import Repairer
	from libs.memory.context_manager import ContextWindowManager
	from libs.modes.chat_mode import ChatModeHandler
	from libs.modes.code_mode import CodeModeHandler
	from libs.modes.command_mode import CommandModeHandler
	from libs.modes.script_mode import ScriptModeHandler
	from libs.modes.vision_mode import VisionModeHandler
	from libs.tools.bootstrap import build_registry

	interp.session_config = SessionConfig.from_args(interp.args)
	interp.prompt_builder = PromptBuilder(interp)
	interp.model_router = ModelRouter(interp)
	interp.executor = CodeExecutor(interp)
	interp.tool_registry = build_registry(interp.executor, interp.package_manager)
	if getattr(getattr(interp, "args", None), "search", False):
		from libs.key_manager import resolve_search_provider

		provider, api_key = resolve_search_provider(
			cli_provider=getattr(interp.args, "search_provider", None),
			cli_api_key=getattr(interp.args, "search_api_key", None),
		)
		interp.tool_registry.enable_web_search(provider=provider, api_key=api_key)
		interp.logger.info("Web search enabled via %s", provider)
	interp.repairer = Repairer(interp)
	interp.code_mode = CodeModeHandler(interp)
	interp.vision_mode = VisionModeHandler(interp)
	interp.script_mode = ScriptModeHandler(interp)
	interp.command_mode = CommandModeHandler(interp)
	interp.chat_mode = ChatModeHandler(interp)
	interp.memory = ContextWindowManager(
		max_tokens=getattr(interp.session_config, "max_context_tokens", 8000),
		history_file=getattr(interp, "history_file", "history/history.json"),
	)
