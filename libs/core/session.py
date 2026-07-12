"""Session configuration and runtime state helpers for the Interpreter orchestrator."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional


def _cli_bool(value: Any, default: bool = False) -> bool:
	"""Coerce CLI flags; MagicMock and other non-bools become *default*."""
	return value if isinstance(value, bool) else default


def _cli_str(value: Any, default: Optional[str] = None) -> Optional[str]:
	"""Coerce optional string CLI args; ignore MagicMock / non-strings."""
	return value if isinstance(value, str) else default


def _cli_str_list(value: Any) -> list[str]:
	"""Coerce --attach style list args; ignore MagicMock."""
	if isinstance(value, (list, tuple)):
		return [str(v) for v in value if isinstance(v, str) and v.strip()]
	if isinstance(value, str) and value.strip():
		return [value.strip()]
	return []


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
	if normalized in ("generate", "project"):
		for attr in modes.values():
			setattr(target, attr, False)
		return
	for key, attr in modes.items():
		setattr(target, attr, normalized == key)


def initialize_mode_from_args(target, args) -> None:
	"""Mirror Interpreter.initialize_mode behavior from CLI args."""
	mode = (getattr(args, "mode", None) or "code").lower()
	# Codegen modes do not enable execution mode flags
	if mode in ("generate", "project"):
		target.CODE_MODE = False
		target.SCRIPT_MODE = False
		target.COMMAND_MODE = False
		target.VISION_MODE = False
		target.CHAT_MODE = False
		target.INTERPRETER_MODE = mode
		return

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


def apply_runtime_settings(interp, settings, *, display_fn, model_exists_fn):
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
		if not model_exists_fn(model):
			display_fn(f"Model {model} does not exists. Please check the model name using '/list' command.")
		else:
			interp.INTERPRETER_MODEL = model
			interp.INTERPRETER_MODEL_LABEL = model
			interp.initialize_client()



	# TUI / CLI parity flags (agentic, sandbox, stream, search, ...)
	args = getattr(interp, "args", None)
	if args is None:
		return

	if "agentic" in settings:
		args.agentic = bool(settings["agentic"])
	if "agent" in settings:
		args.agent = bool(settings["agent"])
		interp.AGENT_MODE = bool(settings["agent"])
	if "gemini_style" in settings:
		args.gemini_style = bool(settings["gemini_style"])
	if "free" in settings:
		args.free = bool(settings["free"])
	if "stream" in settings:
		args.stream = bool(settings["stream"])
	if "search" in settings:
		args.search = bool(settings["search"])
	if "output_format" in settings:
		args.output_format = settings["output_format"]
		if args.output_format in ("json", "markdown"):
			args.stream = False
	if "yolo" in settings:
		args.yolo = bool(settings["yolo"])
	if "yes" in settings:
		args.yes = bool(settings["yes"])
		interp.AUTO_YES = bool(settings["yes"])
	if "verbose" in settings:
		args.verbose = bool(settings["verbose"])
		interp.VERBOSE_UI = bool(settings["verbose"])
	if "science" in settings:
		args.science = bool(settings["science"])
	if "interactive_charts" in settings:
		args.interactive_charts = bool(settings["interactive_charts"])
		data_session = getattr(interp, "data_session", None)
		if data_session is not None and settings["interactive_charts"]:
			data_session.chart_style = "plotly"
	if "safety" in settings and settings["safety"]:
		args.safety = settings["safety"]
		safety_manager = getattr(interp, "safety_manager", None)
		if safety_manager is not None and hasattr(safety_manager, "set_safety_level"):
			try:
				safety_manager.set_safety_level(settings["safety"])
			except Exception:
				pass
	if "sandbox" in settings and settings["sandbox"]:
		from libs.terminal_ui import apply_sandbox_to_args

		apply_sandbox_to_args(args, settings["sandbox"])
		interp.UNSAFE_EXECUTION = bool(args.unsafe)
		interp.SANDBOX_BACKEND = getattr(args, "sandbox_backend", None) or (
			"none" if args.unsafe else "subprocess"
		)
		safety_manager = getattr(interp, "safety_manager", None)
		if safety_manager is not None:
			safety_manager.unsafe_mode = bool(args.unsafe)


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
	interp.AGENT_MODE = _cli_bool(getattr(args, "agent", False))
	interp.AUTO_YES = _cli_bool(getattr(args, "yes", False))
	# --agentic default view shows Thought-only panels; --verbose/-V (or the
	# in-REPL /verbose toggle) restores the full Action/Observation + retry logs.
	interp.VERBOSE_UI = _cli_bool(getattr(args, "verbose", False))
	# Attached local files (#221) — CLI --attach and REPL /file commands.
	from libs.context.file_context import normalize_paths

	interp._attached_files = normalize_paths(_cli_str_list(getattr(args, "attach", None)))
	_ollama = _cli_str(getattr(args, "ollama", None))
	interp.LOCAL_ONLY = _cli_bool(getattr(args, "local", False)) or (_ollama is not None)

	# Data analysis session (#222)
	from libs.data.session_data import DataSession

	interp.data_session = DataSession()
	if _cli_bool(getattr(args, "interactive_charts", False)):
		interp.data_session.chart_style = "plotly"
	eda_path = _cli_str(getattr(args, "eda", None))
	if eda_path:
		try:
			interp.data_session.load_file(eda_path)
			if eda_path not in interp._attached_files:
				interp._attached_files.append(eda_path)
			from libs.data.auto_eda import deterministic_eda_summary

			summary = deterministic_eda_summary(interp.data_session.df)
			print(summary)
			if _cli_bool(getattr(args, "report", False)):
				from libs.output.chart_manager import list_charts
				from libs.output.exporter import export_dataframe

				pdf_path = export_dataframe(
					interp.data_session.df,
					"pdf",
					charts=list_charts(20),
					summary_text=summary,
				)
				print(f"PDF report saved: {pdf_path}")
		except Exception as exc:
			interp.logger.error("Failed --eda load: %s", exc)
			print(f"Failed to load EDA file: {exc}")
			raise
	# Also try loading first --attach into data session
	elif interp._attached_files:
		try:
			interp.data_session.load_file(interp._attached_files[0])
		except Exception as exc:
			interp.logger.warning("Could not ingest attached file into DataSession: %s", exc)

	# R language check (#222)
	lang = str(getattr(args, "lang", "python") or "python").lower()
	if lang in ("r", "rscript"):
		from libs.data.repl_data_commands import check_rscript_available

		if not check_rscript_available():
			print(
				"R language selected but Rscript was not found on PATH. "
				"Install R from https://cran.r-project.org/ and ensure Rscript is available."
			)
		interp.system_message_extra = (
			"You are an R data scientist. Use tidyverse (dplyr, ggplot2, readr) for all data tasks. "
			"Save plots with ggsave()."
		)

	# Structured output (#219) — attach formatter and suppress Rich decorations.
	from libs.output_formatter import OutputFormatter

	formatter = OutputFormatter.from_args(args)
	formatter.apply_env_suppression()
	interp.output_formatter = formatter
	# Piped auto-JSON also must not stream tokens onto stdout.
	if formatter.is_structured and hasattr(args, "stream"):
		args.stream = False

	# Persistent sessions (#218) — load conversation across runs.
	interp.session_store = None
	interp.conversation_history = []
	session_id = getattr(args, "session", None)
	if session_id and isinstance(session_id, str):
		from libs.memory.session_store import SessionStore

		try:
			store = SessionStore(session_id)
		except ValueError as exc:
			interp.logger.error(f"Invalid session id: {exc}")
			raise
		interp.session_store = store
		interp.conversation_history = store.load()
		if interp.conversation_history:
			print(
				f"Resumed session '{session_id}' — "
				f"{len(interp.conversation_history)} messages"
			)
			# Feed prior turns into the in-process history used by prompts.
			interp.history = list(interp.conversation_history)
			interp.INTERPRETER_HISTORY = True
		else:
			print(f"Starting new session '{session_id}'.")

	interp.system_message = load_system_message(interp.INTERPRETER_MODE, interp.logger)
	extra = getattr(interp, "system_message_extra", None)
	if extra:
		interp.system_message = (interp.system_message or "") + "\n\n" + extra
	interp.initialize_client()

	# Ollama model override (#221) after config load — keep api_base from local-model.
	ollama_name = _cli_str(getattr(args, "ollama_model_name", None))
	if ollama_name:
		if interp.config_values is None:
			interp.config_values = {}
		interp.config_values = dict(interp.config_values)
		interp.config_values["model"] = ollama_name
		interp.config_values["provider"] = "ollama"
		# Prefer OpenAI-compatible Ollama endpoint already in local-model.json.
		if not interp.config_values.get("api_base"):
			interp.config_values["api_base"] = "http://localhost:11434/v1"
		interp.INTERPRETER_MODEL = ollama_name
		interp.INTERPRETER_MODEL_LABEL = f"ollama/{ollama_name}"
		interp.logger.info("Ollama model override applied: %s", ollama_name)

	if interp.LOCAL_ONLY:
		attached = getattr(interp, "_attached_files", []) or []
		file_note = ", ".join(attached) if attached else "(none)"
		print(
			"Running in local-only mode — no data leaves your machine.\n"
			f"   Model: {interp.INTERPRETER_MODEL_LABEL or interp.INTERPRETER_MODEL} | "
			f"Files: {file_note}"
		)

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
