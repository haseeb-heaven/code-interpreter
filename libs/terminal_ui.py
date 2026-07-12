"""Selector-based terminal UI for interpreter startup and /settings."""

from argparse import Namespace
import logging
import os
import shlex
import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from libs.utility_manager import UtilityManager

logger = logging.getLogger(__name__)

# Workflow labels shown in TUI (map onto --agentic / --agent / --gemini-style).
WORKFLOW_CLASSIC = "classic"
WORKFLOW_AGENTIC = "agentic (ReAct)"
WORKFLOW_AGENT = "multi-agent pipeline"
WORKFLOW_GEMINI = "gemini-style"

MODE_OPTIONS = ["code", "chat", "script", "command", "vision", "generate", "project"]
WORKFLOW_OPTIONS = [WORKFLOW_CLASSIC, WORKFLOW_AGENTIC, WORKFLOW_AGENT, WORKFLOW_GEMINI]
LANGUAGE_OPTIONS = ["python", "javascript", "r"]
SANDBOX_OPTIONS = ["subprocess", "docker", "off"]
SAFETY_OPTIONS = ["strict", "standard", "relaxed", "off"]
OUTPUT_FORMAT_OPTIONS = ["auto (TTY default)", "plain", "json", "markdown"]


def apply_sandbox_to_args(args, sandbox_choice: str) -> None:
	"""Normalize sandbox / backend / unsafe flags to match ``prepare_args``."""
	choice = (sandbox_choice or "subprocess").strip().lower()
	if choice in ("on", "subprocess"):
		args.sandbox = "subprocess"
		args.sandbox_backend = "subprocess"
		args.unsafe = False
	elif choice == "docker":
		args.sandbox = "docker"
		args.sandbox_backend = "docker"
		args.unsafe = False
	elif choice in ("off", "none", "no"):
		args.sandbox = "off"
		args.sandbox_backend = "none"
		args.unsafe = True
	else:
		args.sandbox = "subprocess"
		args.sandbox_backend = "subprocess"
		args.unsafe = False


def workflow_to_flags(workflow: str) -> dict:
	"""Map a TUI workflow label to agentic/agent/gemini_style/free/stream flags."""
	flags = {
		"agentic": False,
		"agent": False,
		"gemini_style": False,
		"free": False,
		"stream": True,
	}
	if workflow == WORKFLOW_AGENTIC:
		flags["agentic"] = True
	elif workflow == WORKFLOW_AGENT:
		flags["agent"] = True
	elif workflow == WORKFLOW_GEMINI:
		flags["agentic"] = True
		flags["gemini_style"] = True
		flags["free"] = True
		flags["stream"] = True
	return flags


def flags_to_workflow(args) -> str:
	"""Infer the TUI workflow label from an args Namespace / interpreter.args."""
	if getattr(args, "gemini_style", False):
		return WORKFLOW_GEMINI
	if getattr(args, "agentic", False):
		return WORKFLOW_AGENTIC
	if getattr(args, "agent", False):
		return WORKFLOW_AGENT
	return WORKFLOW_CLASSIC


def _parse_path_list(raw: str):
	"""Split a comma/space-separated path string into a list, or None if empty."""
	text = (raw or "").strip()
	if not text:
		return None
	parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
	if len(parts) == 1 and " " in parts[0] and not os.path.exists(parts[0]):
		parts = [p for p in text.split() if p.strip()]
	return parts or None


def _parse_mcp_command(raw: str):
	"""Parse an MCP server command line into an argv list (or None)."""
	text = (raw or "").strip()
	if not text:
		return None
	try:
		parts = shlex.split(text, posix=(os.name != "nt"))
	except ValueError:
		parts = text.split()
	return parts or None


def _output_format_label(value) -> str:
	if value in (None, "", "auto"):
		return "auto (TTY default)"
	return str(value)


def _output_format_value(label: str):
	if not label or label.startswith("auto"):
		return None
	return label


class TerminalUI:
	def __init__(self):
		self.console = Console()
		self.utility_manager = UtilityManager()

	def _read_key(self):
		if os.name == "nt":
			import msvcrt

			key = msvcrt.getwch()
			if key in ("\x00", "\xe0"):
				extended = msvcrt.getwch()
				mapping = {"H": "up", "P": "down", "K": "left", "M": "right"}
				return mapping.get(extended, extended)
			if key == "\r":
				return "enter"
			if key == "\x1b":
				return "escape"
			return key

		import termios
		import tty

		fd = sys.stdin.fileno()
		old_settings = termios.tcgetattr(fd)
		try:
			tty.setraw(fd)
			key = sys.stdin.read(1)
			if key == "\x1b":
				next_chars = sys.stdin.read(2)
				mapping = {"[A": "up", "[B": "down", "[D": "left", "[C": "right"}
				return mapping.get(next_chars, "escape")
			if key in ("\r", "\n"):
				return "enter"
			return key
		finally:
			termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

	def _render_selector(self, title, options, selected_index, help_text, default):
		self.utility_manager.clear_screen()
		visible_rows = max(8, min(14, self.console.size.height - 10))
		start_index = max(0, selected_index - visible_rows // 2)
		end_index = min(len(options), start_index + visible_rows)
		start_index = max(0, end_index - visible_rows)

		table = Table(show_header=True, header_style="bold cyan")
		table.add_column("", width=2)
		table.add_column("Value", overflow="fold")

		for index in range(start_index, end_index):
			option = options[index]
			marker = ">" if index == selected_index else " "
			label = option
			if option == default:
				label += " (default)"
			style = "bold green" if index == selected_index else ""
			table.add_row(marker, label, style=style)

		footer = help_text or "Use Up/Down arrows and Enter to select."
		self.console.print(Panel.fit(footer, title="Interpreter TUI", border_style="green"))
		self.console.print(f"[bold cyan]{title}[/bold cyan]")
		self.console.print(table)
		self.console.print(f"Selected: [bold]{options[selected_index]}[/bold]")

	def _select_option(self, title, options, default, help_text=None):
		if not options:
			raise ValueError(f"No options available for: {title}")

		if not sys.stdin.isatty():
			default_choice = default if default in options else options[0]
			answer = Prompt.ask(f"{title} \\[{'|'.join(options)}]", default=default_choice).strip()
			if answer in options:
				return answer
			for option in options:
				if option.lower() == answer.lower():
					return option
			return default_choice

		try:
			selected_index = options.index(default)
		except ValueError:
			selected_index = 0

		while True:
			self._render_selector(title, options, selected_index, help_text, default)
			key = self._read_key()

			if key in ("up", "k"):
				selected_index = (selected_index - 1) % len(options)
			elif key in ("down", "j"):
				selected_index = (selected_index + 1) % len(options)
			elif key == "enter":
				return options[selected_index]
			elif key == "escape":
				raise KeyboardInterrupt("Selection cancelled by user.")
			elif isinstance(key, str) and len(key) == 1:
				lowered = key.lower()
				for index, option in enumerate(options):
					if option.lower().startswith(lowered):
						selected_index = index
						break

	def _select_boolean(self, title, default=False):
		default_choice = "yes" if default else "no"
		choice = self._select_option(
			title, ["yes", "no"], default_choice, "Use Up/Down arrows and Enter to choose."
		)
		return choice == "yes"

	def _prompt_optional(self, title, default=""):
		"""Text prompt for optional values (session id, paths, MCP command)."""
		answer = Prompt.ask(title, default=default or "")
		return (answer or "").strip()

	def select_mode(self, default_mode="code"):
		default_mode = default_mode if default_mode in MODE_OPTIONS else "code"
		return self._select_option(
			"Mode",
			MODE_OPTIONS,
			default_mode,
			"code/chat/script/command/vision execute or converse; generate/project write code only.",
		)

	def select_workflow(self, default_workflow=WORKFLOW_CLASSIC):
		default_workflow = default_workflow if default_workflow in WORKFLOW_OPTIONS else WORKFLOW_CLASSIC
		return self._select_option(
			"Workflow",
			WORKFLOW_OPTIONS,
			default_workflow,
			"classic REPL, ReAct --agentic, multi-agent --agent, or gemini-style (agentic + free).",
		)

	def select_model(self, default_model=None):
		models = self.utility_manager.list_available_models()
		default_model = default_model or self.utility_manager.get_default_model_name()
		if default_model not in models:
			default_model = models[0]
		return self._select_option(
			"Model",
			models,
			default_model,
			"Use Up/Down arrows, Enter, or type the first letter to jump.",
		)

	def select_free_model(self, default_model=None):
		"""Pick from curated free/cheap presets (configs/models.toml [[free_catalog]])."""
		try:
			from libs.free_llms import FreeLLMCatalog

			catalog = FreeLLMCatalog.load()
			configs = catalog.list_configs()
		except Exception as exc:
			logger.warning("Failed to load free LLM catalog: %s", exc)
			configs = []

		if not configs:
			self.console.print("[yellow]No free presets found; falling back to all models.[/yellow]")
			return self.select_model(default_model)

		default = default_model if default_model in configs else configs[0]
		return self._select_option(
			"Free / cheap model",
			configs,
			default,
			"Curated free/cheap presets (--free / configs/models.toml [[free_catalog]]).",
		)

	def select_language(self, default_lang="python"):
		default_lang = (default_lang or "python").lower()
		if default_lang in ("rscript",):
			default_lang = "r"
		if default_lang not in LANGUAGE_OPTIONS:
			default_lang = "python"
		return self._select_option("Language", LANGUAGE_OPTIONS, default_lang)

	def select_sandbox(self, default_sandbox="subprocess"):
		choice = (default_sandbox or "subprocess").lower()
		if choice in ("on", "none"):
			choice = "subprocess" if choice == "on" else "off"
		if choice not in SANDBOX_OPTIONS:
			choice = "subprocess"
		return self._select_option(
			"Sandbox",
			SANDBOX_OPTIONS,
			choice,
			"subprocess (default), docker (strong isolation), or off (UNSAFE).",
		)

	def select_safety(self, default_safety="standard"):
		choice = default_safety if default_safety in SAFETY_OPTIONS else "standard"
		return self._select_option(
			"Safety level",
			SAFETY_OPTIONS,
			choice,
			"strict / standard / relaxed / off - mirrors --safety.",
		)

	def select_output_format(self, default_format=None):
		default_label = _output_format_label(default_format)
		if default_label not in OUTPUT_FORMAT_OPTIONS:
			default_label = OUTPUT_FORMAT_OPTIONS[0]
		label = self._select_option(
			"Output format",
			OUTPUT_FORMAT_OPTIONS,
			default_label,
			"auto uses plain on TTY / JSON when piped; json/markdown disable live streaming.",
		)
		return _output_format_value(label)

	def select_boolean(self, title, default=False):
		return self._select_boolean(title, default=default)

	def _collect_core_settings(self, *, mode_default, workflow_default, model_default,
							   lang_default, free_default, sandbox_default, safety_default,
							   display_default, exec_default, save_default, history_default,
							   stream_default, search_default, output_format_default):
		"""Shared selectors for launch() and interactive_settings()."""
		mode = self.select_mode(mode_default)
		workflow = self.select_workflow(workflow_default)
		wf_flags = workflow_to_flags(workflow)

		prefer_free = bool(free_default) or wf_flags["free"]
		if not wf_flags["free"]:
			prefer_free = self._select_boolean(
				"Prefer free/cheap LLM presets (--free)?",
				default=prefer_free,
			)
		else:
			prefer_free = True

		if prefer_free:
			model = self.select_free_model(model_default)
		else:
			model = self.select_model(model_default)

		language = self.select_language(lang_default)
		sandbox = self.select_sandbox(sandbox_default)
		safety = self.select_safety(safety_default)

		display_code = display_default
		execute_code = exec_default
		save_code = save_default
		if mode in ["code", "script", "command", "generate", "project"] and not display_code:
			display_code = self._select_boolean("Display generated code automatically?", default=True)
		if mode == "code" and not execute_code:
			execute_code = self._select_boolean("Execute generated code automatically?", default=False)
		if mode in ["code", "script", "command"] and not save_code:
			save_code = self._select_boolean("Save generated output automatically?", default=False)

		history = history_default
		if not history:
			history = self._select_boolean("Enable history memory?", default=False)

		if wf_flags.get("gemini_style"):
			stream = True
		else:
			stream = self._select_boolean("Stream LLM tokens (--stream)?", default=bool(stream_default))

		search = self._select_boolean("Enable web search (--search)?", default=bool(search_default))
		output_format = self.select_output_format(output_format_default)

		settings = {
			"mode": mode,
			"workflow": workflow,
			"model": model,
			"language": language,
			"display_code": display_code,
			"execute_code": execute_code,
			"save_code": save_code,
			"history": history,
			"free": prefer_free or wf_flags["free"],
			"stream": stream,
			"search": search,
			"sandbox": sandbox,
			"safety": safety,
			"output_format": output_format,
			"agentic": wf_flags["agentic"],
			"agent": wf_flags["agent"],
			"gemini_style": wf_flags["gemini_style"],
		}
		if wf_flags["gemini_style"]:
			settings["free"] = True
			settings["stream"] = True
		return settings

	def _collect_advanced_settings(self, args):
		"""Optional advanced flags: session, yolo, yes, science, charts, image, attach, mcp."""
		advanced = {
			"session": getattr(args, "session", None),
			"yolo": bool(getattr(args, "yolo", False)),
			"yes": bool(getattr(args, "yes", False)),
			"science": bool(getattr(args, "science", False)),
			"interactive_charts": bool(getattr(args, "interactive_charts", False)),
			"image": getattr(args, "image", None),
			"attach": getattr(args, "attach", None),
			"mcp_server": getattr(args, "mcp_server", None),
		}

		configure_more = self._select_boolean(
			"Configure advanced options (session, YOLO, images, MCP, ...)?",
			default=False,
		)
		if not configure_more:
			# "no" (including the default) must genuinely skip every subsequent
			# advanced prompt -- session, YOLO, yes, science, charts, image,
			# attach, MCP -- and fall back to whatever was already on ``args``.
			return advanced

		session_raw = self._prompt_optional(
			"Session name (--session, blank to skip)",
			default=advanced["session"] or "",
		)
		advanced["session"] = session_raw or None
		advanced["yolo"] = self._select_boolean(
			"YOLO mode - auto-approve tool calls (--yolo)?",
			default=advanced["yolo"],
		)
		advanced["yes"] = self._select_boolean(
			"Auto-confirm prompts (--yes)?",
			default=advanced["yes"],
		)
		advanced["science"] = self._select_boolean(
			"Scientific computing prompt (--science)?",
			default=advanced["science"],
		)
		advanced["interactive_charts"] = self._select_boolean(
			"Prefer Plotly interactive charts (--interactive-charts)?",
			default=advanced["interactive_charts"],
		)

		image_raw = self._prompt_optional(
			"Image path(s) for vision (--image, comma-separated, blank to skip)",
			default=",".join(advanced["image"] or []) if advanced["image"] else "",
		)
		advanced["image"] = _parse_path_list(image_raw)

		attach_raw = self._prompt_optional(
			"Attach file path(s) (--attach, comma-separated, blank to skip)",
			default=",".join(advanced["attach"] or []) if advanced["attach"] else "",
		)
		advanced["attach"] = _parse_path_list(attach_raw)

		mcp_raw = self._prompt_optional(
			"MCP server command (--mcp-server, blank to skip)",
			default=" ".join(advanced["mcp_server"]) if advanced["mcp_server"] else "",
		)
		advanced["mcp_server"] = _parse_mcp_command(mcp_raw)
		return advanced

	def _collect_codegen_task(self, existing_task=None, existing_file=None):
		"""Prompt for the ``--task`` text (or ``-f`` prompt file) that ``generate``/``project``
		mode requires.

		``resolve_codegen_task`` (libs/code_generator.py) always raises ``ValueError`` when both
		are empty, so unlike the other wizard answers these have no valid blank default. Retry a
		bounded number of times, then exit cleanly instead of letting the caller hit that
		unhandled ``ValueError``.
		"""
		task = (existing_task or "").strip() if isinstance(existing_task, str) else ""
		file_path = existing_file.strip() if isinstance(existing_file, str) else ""
		if task or file_path:
			return {"task": task or None, "file": file_path or None}

		max_attempts = 3
		for attempt in range(max_attempts):
			task = self._prompt_optional(
				"Task description for code generation (--task; required for generate/project mode)"
			)
			if task:
				return {"task": task, "file": None}
			file_path = self._prompt_optional(
				"Prompt file path instead (-f, e.g. prompt.txt; blank to re-enter task text)"
			)
			if file_path:
				return {"task": None, "file": file_path}
			if attempt < max_attempts - 1:
				self.console.print(
					"[yellow]Generate/project mode needs either a task description or a "
					"prompt file path.[/yellow]"
				)

		self.console.print(
			"[red]No task description or prompt file provided; cannot continue in "
			"generate/project mode. Re-run with --task TEXT or -f prompt.txt.[/red]"
		)
		raise SystemExit(1)

	def interactive_settings(self, interpreter):
		current_model = getattr(interpreter, "INTERPRETER_MODEL_LABEL", None) or getattr(
			interpreter, "INTERPRETER_MODEL", None
		)
		current_mode = getattr(interpreter, "INTERPRETER_MODE", "code")
		current_lang = getattr(interpreter, "INTERPRETER_LANGUAGE", "python")
		args = getattr(interpreter, "args", None) or Namespace()

		settings = self._collect_core_settings(
			mode_default=current_mode,
			workflow_default=flags_to_workflow(args),
			model_default=current_model,
			lang_default=current_lang,
			free_default=bool(getattr(args, "free", False)),
			sandbox_default=getattr(args, "sandbox", "subprocess") or "subprocess",
			safety_default=getattr(args, "safety", "standard") or "standard",
			display_default=getattr(interpreter, "DISPLAY_CODE", False),
			exec_default=getattr(interpreter, "EXECUTE_CODE", False),
			save_default=getattr(interpreter, "SAVE_CODE", False),
			history_default=getattr(interpreter, "INTERPRETER_HISTORY", False),
			stream_default=bool(getattr(args, "stream", True)),
			search_default=bool(getattr(args, "search", False)),
			output_format_default=getattr(args, "output_format", None),
		)
		return settings

	def launch(self, args):
		"""Run startup selectors and return a full Namespace matching CLI flags."""
		out = Namespace(**vars(args))

		core = self._collect_core_settings(
			mode_default=args.mode or "code",
			workflow_default=flags_to_workflow(args),
			model_default=args.model or self.utility_manager.get_default_model_name(),
			lang_default=args.lang or "python",
			free_default=bool(getattr(args, "free", False)),
			sandbox_default=getattr(args, "sandbox", "subprocess") or "subprocess",
			safety_default=getattr(args, "safety", "standard") or "standard",
			display_default=bool(getattr(args, "display_code", False)),
			exec_default=bool(getattr(args, "exec", False)),
			save_default=bool(getattr(args, "save_code", False)),
			history_default=bool(getattr(args, "history", False)),
			stream_default=bool(getattr(args, "stream", True)),
			search_default=bool(getattr(args, "search", False)),
			output_format_default=getattr(args, "output_format", None),
		)

		self.utility_manager.clear_screen()
		self.console.print(
			Panel.fit(
				(
					f"Mode: [bold]{core['mode']}[/bold] | "
					f"Workflow: [bold]{core['workflow']}[/bold] | "
					f"Model: [bold]{core['model']}[/bold] | "
					f"Language: [bold]{core['language']}[/bold]"
				),
				title="Interpreter Session",
				border_style="blue",
			)
		)

		codegen = None
		if core["mode"] in ("generate", "project"):
			codegen = self._collect_codegen_task(
				existing_task=getattr(args, "task", None),
				existing_file=getattr(args, "file", None),
			)

		advanced = self._collect_advanced_settings(args)

		out.mode = core["mode"]
		out.model = core["model"]
		out.lang = core["language"]
		out.display_code = core["display_code"]
		out.exec = core["execute_code"]
		out.save_code = core["save_code"]
		out.history = core["history"]
		out.agentic = core["agentic"]
		out.agent = core["agent"]
		out.gemini_style = core["gemini_style"]
		out.free = core["free"]
		out.stream = core["stream"]
		out.search = core["search"]
		out.output_format = core["output_format"]
		out.safety = core["safety"]
		apply_sandbox_to_args(out, core["sandbox"])

		out.session = advanced["session"]
		out.yolo = advanced["yolo"]
		out.yes = advanced["yes"]
		out.science = advanced["science"]
		out.interactive_charts = advanced["interactive_charts"]
		out.image = advanced["image"]
		out.attach = advanced["attach"]
		out.mcp_server = advanced["mcp_server"]

		if codegen is not None:
			out.task = codegen["task"]
			out.file = codegen["file"]

		if out.output_format in ("json", "markdown"):
			out.stream = False

		out.tui = True
		out.cli = False
		return out
