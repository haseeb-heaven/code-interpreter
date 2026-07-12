"""
Interpreter orchestrator — wires modular components together.

Public method/attribute surface is preserved for the existing test suite.
Implementation lives in ``libs.core.*``, ``libs.execution.*``, and ``libs.modes.*``.
"""

from __future__ import annotations

import os
import time

import litellm
from dotenv import load_dotenv
from rich.console import Console

from libs.code_interpreter import CodeInterpreter
from libs.core.main_loop import run_interpreter_main
from libs.core.model_router import ModelRouter
from libs.core.session import (
	apply_mode_flags,
	apply_runtime_settings,
	bootstrap_interpreter,
	display_session_banner,
	initialize_mode_from_args,
	open_tui_settings,
	wire_components,
)
from libs.execution.repairer import RepairCircuitBreaker  # noqa: F401 — re-export
from libs.execution.sandbox_toggle import toggle_sandbox_mode
from libs.history_manager import History
from libs.logger import Logger
from libs.markdown_code import display_code, display_markdown_message
from libs.modes.code_mode import CodeModeHandler
from libs.package_manager import PackageManager
from libs.repl_guards import format_short_llm_error, is_non_task_input, is_unknown_slash_command  # noqa: F401
from libs.safety_manager import ExecutionSafetyManager, SafetyLevel
from libs.terminal_ui import TerminalUI
from libs.utility_manager import UtilityManager

litellm.set_verbose = False
litellm.suppress_debug_info = True
litellm.telemetry = False

MAX_OUTPUT = 10_000_000
MAX_TIMEOUT = 300


class Interpreter:
	logger = None
	client = None
	interpreter_version = None
	console = Console()

	def __init__(self, args):
		self.args = args
		self.history, self.history_count, self.history_file = [], 3, "history/history.json"
		self.utility_manager, self.package_manager = UtilityManager(), PackageManager()
		self.history_manager = History(self.history_file)
		self.logger = Logger.initialize("logs/interpreter.log")
		self.client = self.config_values = self.gemini_vision = None
		self.system_message = ""
		self._pending_images = []
		self._last_response_was_streamed = False
		_unsafe = getattr(args, "unsafe", False)
		self.UNSAFE_EXECUTION = _unsafe if isinstance(_unsafe, bool) else False
		safety_level = getattr(args, "safety", None)
		# MagicMock attrs are truthy objects — only accept real strings/enums.
		if not isinstance(safety_level, (str, SafetyLevel)) and safety_level is not None:
			safety_level = None
		self.safety_manager = ExecutionSafetyManager(
			unsafe_mode=self.UNSAFE_EXECUTION,
			safety_level=safety_level,
		)
		# Keep flags aligned after SafetyLevel resolution.
		self.UNSAFE_EXECUTION = bool(self.safety_manager.unsafe_mode)
		self.code_interpreter = CodeInterpreter(safety_manager=self.safety_manager)
		try:
			self.EXECUTION_TIMEOUT = int(getattr(args, "timeout", 30) or 30)
		except (TypeError, ValueError):
			self.EXECUTION_TIMEOUT = 30
		_backend = getattr(args, "sandbox_backend", None)
		if not isinstance(_backend, str):
			_backend = None
		self.SANDBOX_BACKEND = _backend or (
			"none" if self.UNSAFE_EXECUTION else "subprocess"
		)
		self.MAX_REPAIR_ATTEMPTS, self.MAX_LLM_RETRIES = 3, 3
		self.terminal_ui = TerminalUI() if getattr(args, "tui", False) else None
		self._last_execution_approved = False
		wire_components(self)
		self.initialize()

	def initialize(self):
		bootstrap_interpreter(self)

	def initialize_client(self):
		return self.model_router.initialize_client(load_dotenv_fn=load_dotenv, getenv_fn=os.getenv, environ=os.environ)

	def initialize_mode(self):
		initialize_mode_from_args(self, self.args)

	def _apply_mode(self, mode):
		apply_mode_flags(self, mode)

	def _display_session_banner(self, os_name, input_prompt_mode):
		display_session_banner(
			self.console, unsafe=self.UNSAFE_EXECUTION, os_name=os_name,
			language=self.INTERPRETER_LANGUAGE, mode=self.INTERPRETER_MODE,
			input_prompt_mode=input_prompt_mode,
			model_label=self.INTERPRETER_MODEL_LABEL or self.INTERPRETER_MODEL,
		)

	def _is_recoverable_runtime_error(self, error_text):
		return ModelRouter.is_recoverable_runtime_error(error_text)

	def _format_runtime_error_message(self, error_text):
		return ModelRouter.format_runtime_error_message(error_text)

	def _is_retryable_request_error(self, error_text):
		return ModelRouter.is_retryable_request_error(error_text)

	def _generate_content_with_retries(self, message, chat_history, config_values=None, image_file=None):
		return self.model_router.generate_content_with_retries(
			message, chat_history, config_values=config_values, image_file=image_file,
			sleep_fn=time.sleep, display_fn=display_markdown_message,
		)

	async def _generate_content_with_retries_async(self, message, chat_history, config_values=None, image_file=None):
		return await self.model_router.generate_content_with_retries_async(
			message, chat_history, config_values=config_values, image_file=image_file,
			display_fn=display_markdown_message,
		)

	def get_prompt(self, message, chat_history):
		return self.prompt_builder.get_prompt(message, chat_history)

	def get_code_prompt(self, task, os_name):
		return self.prompt_builder.get_code_prompt(task, os_name)

	def get_script_prompt(self, task, os_name):
		return self.prompt_builder.get_script_prompt(task, os_name)

	def get_command_prompt(self, task, os_name):
		return self.prompt_builder.get_command_prompt(task, os_name)

	def handle_vision_mode(self, task):
		return self.prompt_builder.handle_vision_mode(task)

	def handle_chat_mode(self, task):
		return self.prompt_builder.handle_chat_mode(task)

	def get_mode_prompt(self, task, os_name):
		return self.prompt_builder.get_mode_prompt(task, os_name)

	def _maybe_simplify_generated_code(self, task, code_snippet):
		return self.code_mode.maybe_simplify_generated_code(task, code_snippet)

	def _task_has_any(self, text, phrases):
		return CodeModeHandler.task_has_any(text, phrases)

	def _is_simple_directory_listing_task(self, task_lower):
		return self.code_mode.is_simple_directory_listing_task(task_lower)

	def _execute_generated_output(self, code_snippet, code_lang, force_execute=False):
		return self.executor.execute_generated_output(code_snippet, code_lang, force_execute=force_execute)

	def execute_code(self, code, language, sandbox_context=None, force_execute=False):
		return self.executor.execute_code(code, language, sandbox_context=sandbox_context, force_execute=force_execute)

	def execute_last_code(self, os_name):
		return self.executor.execute_last_code(os_name, display_code_fn=display_code, display_markdown_fn=display_markdown_message)

	def _build_repair_prompt(self, task, prompt, code_snippet, error_text, os_name, code_output=None):
		return self.repairer.build_repair_prompt(task, prompt, code_snippet, error_text, os_name, code_output=code_output)

	def _attempt_repair_after_failure(self, *args, **kwargs):
		return self.repairer.attempt_repair_after_failure(
			*args, display_code_fn=display_code, display_markdown_fn=display_markdown_message, **kwargs,
		)

	def _extract_latest_user_text(self, message, messages):
		return ModelRouter.extract_latest_user_text(message, messages)

	def _run_openai_compatible_completion(self, api_key_name, messages, temperature, max_tokens, api_base, extra_headers=None):
		return self.model_router.run_openai_compatible_completion(
			api_key_name, messages, temperature, max_tokens, api_base, extra_headers=extra_headers,
			completion_fn=litellm.completion, getenv_fn=os.getenv,
		)

	def _generate_browser_use_content(self, message, messages, config_values):
		return self.model_router.generate_browser_use_content(message, messages, config_values, getenv_fn=os.getenv)

	async def _generate_browser_use_content_async(self, message, messages, config_values):
		return await self.model_router.generate_browser_use_content_async(
			message, messages, config_values, getenv_fn=os.getenv
		)

	def generate_content(self, message, chat_history, temperature=0.1, max_tokens=1024, config_values=None, image_file=None):
		return self.model_router.generate_content(
			message, chat_history, temperature=temperature, max_tokens=max_tokens,
			config_values=config_values, image_file=image_file,
			completion_fn=litellm.completion, getenv_fn=os.getenv,
		)

	def _safe_input(self, prompt_text, default=None):
		"""Read user input, or auto-confirm when ``--yes`` / CI non-interactive mode is on."""
		auto_yes = bool(getattr(self, "AUTO_YES", False))
		text = prompt_text or ""
		lower = text.lower()
		if auto_yes and (
			"y/n" in lower
			or "execute the" in lower
			or "create a new prompt" in lower
			or "are you sure" in lower
		):
			self.logger.info(f"AUTO_YES confirmed prompt: {text.strip()!r}")
			return "y"
		if auto_yes and default is not None:
			self.logger.info(f"AUTO_YES default for prompt: {text.strip()!r} -> {default!r}")
			return default
		try:
			return input(prompt_text)
		except EOFError:
			return default

	def _structured_output_active(self) -> bool:
		"""True when ``--output-format json|markdown`` (or piped auto-JSON) is active."""
		formatter = getattr(self, "output_formatter", None)
		return bool(formatter is not None and formatter.is_structured)

	def emit_turn_result(
		self,
		result_text="",
		code=None,
		execution_output=None,
		error=None,
		status="success",
	):
		"""Emit structured result for the completed turn (#219). Plain mode is a no-op."""
		formatter = getattr(self, "output_formatter", None)
		if formatter is None:
			return
		if error and status == "success":
			status = "error"
		formatter.emit(
			result_text=result_text or "",
			code=code,
			execution_output=execution_output,
			error=error,
			status=status,
			language=getattr(self, "INTERPRETER_LANGUAGE", None) or "python",
		)

	def record_session_turn(
		self,
		task,
		prompt=None,
		code_snippet=None,
		code_output=None,
		code_error=None,
		os_name=None,
	):
		"""Append one completed turn and auto-save when ``--session`` is active (#218)."""
		if getattr(self, "session_store", None) is None:
			return
		entry = {
			"assistant": {
				"task": task,
				"mode": getattr(self, "INTERPRETER_MODE", None),
				"os": os_name,
				"language": getattr(self, "INTERPRETER_LANGUAGE", None),
				"model": getattr(self, "INTERPRETER_MODEL", None),
			},
			"user": prompt if prompt is not None else task,
			"system": {
				"code": code_snippet,
				"output": code_output,
				"error": code_error,
			},
		}
		history = getattr(self, "conversation_history", None)
		if history is None:
			self.conversation_history = []
			history = self.conversation_history
		history.append(entry)
		self._after_turn()

	def _after_turn(self):
		"""Called after each completed LLM turn. Auto-saves if session is active."""
		store = getattr(self, "session_store", None)
		history = getattr(self, "conversation_history", None) or []
		if store and history:
			store.save(
				messages=history,
				model=str(getattr(self, "INTERPRETER_MODEL", "") or ""),
			)

	def handle_session_command(self, task: str) -> bool:
		"""Handle ``/session`` and ``/sessions`` REPL commands. Return True if handled."""
		import time

		from libs.memory.session_store import SessionStore

		lower = (task or "").strip().lower()
		if lower == "/sessions":
			sessions = SessionStore.list_sessions()
			if not sessions:
				print("No saved sessions found.")
			else:
				print(f"\n{'SESSION ID':<25} {'MESSAGES':>8} {'MODEL':<20} LAST UPDATED")
				print("-" * 75)
				for s in sessions:
					updated = time.strftime(
						"%Y-%m-%d %H:%M", time.localtime(s["updated_at"] or 0)
					)
					print(
						f"{s['session_id']:<25} {s['message_count']:>8} "
						f"{s['model']:<20} {updated}"
					)
			return True

		if not lower.startswith("/session"):
			return False

		parts = (task or "").split()
		sub = parts[1].lower() if len(parts) > 1 else "info"
		store = getattr(self, "session_store", None)

		if sub == "save":
			if not store:
				print("No active session. Start with --session <id>.")
			else:
				self._after_turn()
				print(f"Session '{store.session_id}' saved "
					  f"({len(getattr(self, 'conversation_history', []) or [])} messages).")
			return True

		if sub == "clear":
			if not store:
				print("No active session. Start with --session <id>.")
			else:
				self.conversation_history = []
				self.history = []
				store.clear()
				print(f"Session '{store.session_id}' cleared.")
			return True

		if sub == "info":
			if not store:
				print("No active session. Start with --session <id>.")
			else:
				meta = store.get_metadata() or {
					"session_id": store.session_id,
					"message_count": len(getattr(self, "conversation_history", []) or []),
					"model": getattr(self, "INTERPRETER_MODEL", ""),
					"updated_at": None,
				}
				print(
					f"Session: {meta.get('session_id')} | "
					f"messages={meta.get('message_count', 0)} | "
					f"model={meta.get('model', '')}"
				)
			return True

		print("Usage: /session save|clear|info  or  /sessions")
		return True

	def _open_tui_settings(self, setting_type):
		self._ensure_terminal_ui()
		return open_tui_settings(self, setting_type)

	def _apply_runtime_settings(self, settings):
		apply_runtime_settings(self, settings, display_fn=display_markdown_message, path_isfile=os.path.isfile)

	def _ensure_terminal_ui(self):
		"""Lazily create TerminalUI so slash pickers work under ``--cli`` too."""
		if getattr(self, "terminal_ui", None) is None:
			self.terminal_ui = TerminalUI()
		return self.terminal_ui

	def _prefer_free_model_picker(self) -> bool:
		args = getattr(self, "args", None)
		return bool(
			getattr(args, "free", False)
			or getattr(args, "gemini_style", False)
			or getattr(args, "agentic", False)
			or getattr(args, "yolo", False)
		)

	def _list_valid_model_configs(self, limit: int = 24) -> list:
		from libs.free_llms import list_config_names

		names = list_config_names("configs")
		if not names and hasattr(self, "utility_manager") and self.utility_manager:
			try:
				names = list(self.utility_manager.list_available_models())
			except Exception:
				names = []
		return names[: max(0, int(limit))]

	def _switch_model_config(self, config_name: str, *, on_switched=None) -> bool:
		"""Apply a resolved config basename; return True on success."""
		from libs.free_llms import resolve_model_config_name

		resolved = resolve_model_config_name(config_name) or (
			config_name if os.path.isfile(f"configs/{config_name}.json") else None
		)
		if not resolved:
			return False
		self.INTERPRETER_MODEL = resolved
		self.INTERPRETER_MODEL_LABEL = resolved
		try:
			self.initialize_client()
		except Exception as exc:
			self.logger.error(f"Failed to initialize client for {resolved}: {exc}")
		if callable(on_switched):
			on_switched(resolved)
		self.console.print(f"Model switched to [bold]{resolved}[/bold]")
		return True

	def _open_model_picker(self, *, on_switched=None) -> None:
		"""Open TUI model / free-model picker and apply the selection."""
		ui = self._ensure_terminal_ui()
		default = self.INTERPRETER_MODEL_LABEL or self.INTERPRETER_MODEL
		if self._prefer_free_model_picker() and hasattr(ui, "select_free_model"):
			chosen = ui.select_free_model(default)
		else:
			chosen = ui.select_model(default)
		if chosen:
			if not self._switch_model_config(chosen, on_switched=on_switched):
				self.console.print(
					f"[yellow]Selected model '{chosen}' has no configs/{chosen}.json[/yellow]"
				)

	def _handle_model_slash_command(self, raw: str, *, on_switched=None) -> None:
		"""``/model`` → TUI picker; ``/model <name>`` → resolve config or open picker."""
		from libs.free_llms import resolve_model_config_name

		parts = (raw or "").split(maxsplit=1)
		name = parts[1].strip() if len(parts) > 1 else ""
		if not name:
			self._open_model_picker(on_switched=on_switched)
			return

		resolved = resolve_model_config_name(name)
		if resolved:
			self._switch_model_config(resolved, on_switched=on_switched)
			return

		valid = self._list_valid_model_configs()
		self.console.print(
			f"[yellow]Model '{name}' is not a valid config name.[/yellow] "
			"Use a configs/<name>.json basename (e.g. gemini-2.5-flash), not a raw LiteLLM id "
			"unless that config exists."
		)
		if valid:
			preview = ", ".join(valid[:12])
			more = f" (+{len(valid) - 12} more)" if len(valid) > 12 else ""
			self.console.print(f"Valid configs include: {preview}{more}")
		self._open_model_picker(on_switched=on_switched)

	def _handle_free_slash_command(self, *, on_switched=None) -> None:
		"""``/free`` opens the free-catalog TUI picker (also prints the table)."""
		from libs.free_llms import FreeLLMCatalog

		print(FreeLLMCatalog.load().format_table())
		ui = self._ensure_terminal_ui()
		default = self.INTERPRETER_MODEL_LABEL or self.INTERPRETER_MODEL
		chosen = ui.select_free_model(default) if hasattr(ui, "select_free_model") else None
		if chosen:
			self._switch_model_config(chosen, on_switched=on_switched)

	def _get_subprocess_security_kwargs(self, sandbox_context=None):
		return self.code_interpreter._get_subprocess_security_kwargs(sandbox_context=sandbox_context)

	def toggle_sandbox_mode(self):
		return toggle_sandbox_mode(self, display_fn=display_markdown_message, input_fn=self._safe_input)

	def run_agent_pipeline(self, task, os_name):
		"""Execute one task through the multi-agent pipeline and return AgentContext."""
		from libs.agents.agent_pipeline import AgentPipeline

		pipeline = AgentPipeline(
			model_router=self.model_router,
			executor=self.executor,
			repairer=self.repairer,
			prompt_builder=self.prompt_builder,
			logger=self.logger,
			unsafe=self.UNSAFE_EXECUTION,
			code_extractor=self.code_interpreter.extract_code,
			display_code_fn=display_code,
			display_markdown_fn=display_markdown_message,
		)
		return pipeline.run(task=task, os_name=os_name, language=self.INTERPRETER_LANGUAGE)

	async def run_agent_pipeline_async(self, task, os_name):
		"""Execute one task through the preferred async multi-agent pipeline."""
		from libs.agents.agent_pipeline import AgentPipeline

		pipeline = AgentPipeline(
			model_router=self.model_router,
			executor=self.executor,
			repairer=self.repairer,
			prompt_builder=self.prompt_builder,
			logger=self.logger,
			unsafe=self.UNSAFE_EXECUTION,
			code_extractor=self.code_interpreter.extract_code,
			display_code_fn=display_code,
			display_markdown_fn=display_markdown_message,
		)
		return await pipeline.run_async(task=task, os_name=os_name, language=self.INTERPRETER_LANGUAGE)

	def interpreter_auto_main(self):
		"""Run the autonomous FS/shell tool loop (#215), optionally with MCP tools.

		``--yolo`` skips tool-call approval. ``--mcp-server CMD...`` attaches an MCP server.
		"""
		from libs.agent.auto_loop import AutonomousAgentLoop
		from libs.memory import ContextManager
		from libs.tools.bootstrap import build_native_fs_registry

		one_shot = bool(getattr(self, "INTERPRETER_PROMPT_FILE", False) and getattr(self.args, "file", None))
		auto_mode = bool(getattr(self.args, "yolo", False))
		mcp_cmd = getattr(self.args, "mcp_server", None)
		mcp_client = None

		try:
			mode_label = "YOLO (no approval)" if auto_mode else "tool loop (confirm each call)"
			self.console.print(f"[bold cyan]Autonomous agent loop[/bold cyan] — {mode_label}")
			self.console.print(
				f"Model: [bold]{self.INTERPRETER_MODEL}[/bold]  ·  "
				"Commands: /free  /model  /help  /exit"
			)

			registry = build_native_fs_registry()
			if getattr(self.args, "search", False):
				from libs.key_manager import resolve_search_provider

				provider, api_key = resolve_search_provider(
					cli_provider=getattr(self.args, "search_provider", None),
					cli_api_key=getattr(self.args, "search_api_key", None),
				)
				registry.enable_web_search(provider=provider, api_key=api_key)
				self.console.print(f"[green]Web search enabled[/green] ({provider})")

			if mcp_cmd:
				from libs.mcp import MCPClient

				mcp_client = MCPClient(list(mcp_cmd))
				mcp_client.start_sync()
				mcp_tools = mcp_client.list_tools_sync()
				registry.register_mcp_tools(mcp_tools, mcp_client.call_tool_sync)
				self.console.print(
					f"[green]MCP connected[/green]: {' '.join(mcp_cmd)} "
					f"({len(mcp_tools)} tools)"
				)

			def on_fallback(candidate):
				config_name = str(candidate.get("config") or "").strip()
				if config_name:
					self.INTERPRETER_MODEL = config_name
					self.INTERPRETER_MODEL_LABEL = config_name
					try:
						self.initialize_client()
					except Exception:
						pass
					self.console.print(
						f"[yellow]Fell back to[/yellow] [bold]{config_name}[/bold]"
					)

			context_manager = ContextManager(token_limit=100_000, preserve_last_n=6)
			# Prefer config basename so free-catalog fallback can rotate providers.
			loop = AutonomousAgentLoop(
				model=str(self.INTERPRETER_MODEL),
				auto_mode=auto_mode,
				registry=registry,
				enable_free_fallback=True,
				on_fallback=on_fallback,
				context_manager=context_manager,
			)

			file_task = None
			if one_shot:
				try:
					with open(self.args.file, "r", encoding="utf-8") as file:
						file_task = file.read()
				except Exception as exc:
					self.logger.error(f"Error reading prompt file: {exc}")
					return

			while True:
				if file_task is not None:
					task = file_task
					file_task = None
				else:
					task = self._safe_input("Enter your task: ", default="")

				raw = (task or "").strip()
				if not raw:
					self.console.print("Task cannot be empty.")
					if one_shot:
						return
					continue

				lower = raw.lower()
				if lower in ("/exit", "exit", "quit", "/quit"):
					self.console.print("Exiting autonomous mode.")
					return
				if lower in ("/help", "help"):
					self.console.print(
						"Autonomous commands:\n"
						"  /free           Free-catalog table + interactive picker\n"
						"  /model          Interactive model picker (TUI)\n"
						"  /model <name>   Switch to configs/<name>.json\n"
						"  /settings       Interactive settings (TUI)\n"
						"  /tools          List registered tools\n"
						"  /help           Show this help\n"
						"  /exit           Leave the autonomous REPL\n"
						"Or type a natural-language task to run the tool loop."
					)
					if one_shot:
						return
					continue
				if lower in ("/settings", "/mode"):
					setting = "settings" if lower == "/settings" else "mode"
					self._apply_runtime_settings(self._open_tui_settings(setting))
					if one_shot:
						return
					continue
				if lower == "/tools":
					for schema in registry.list_tools():
						self.console.print(f"  - {schema.get('name')}: {schema.get('description', '')}")
					if one_shot:
						return
					continue
				if lower == "/free":
					self._handle_free_slash_command(
						on_switched=lambda name: setattr(loop, "model", name)
					)
					if one_shot:
						return
					continue
				if lower == "/model" or lower.startswith("/model "):
					self._handle_model_slash_command(
						raw,
						on_switched=lambda name: setattr(loop, "model", name),
					)
					if one_shot:
						return
					continue

				result = loop.run(raw)
				self.console.print(result or "(no output)")
				if one_shot:
					return
		except KeyboardInterrupt:
			self.console.print("\n[bold red]Autonomous workflow interrupted by user.[/bold red]")
		finally:
			if mcp_client is not None:
				try:
					mcp_client.stop_sync()
				except Exception:
					pass

	def interpreter_agentic_main(self):
		"""Run the ReAct agentic loop (Thought -> Action -> Observation).

		Interactive sessions stay in a Gemini-CLI-like REPL until ``/exit``.
		A ``-f`` / prompt-file run remains one-shot for scripts/CI.
		"""
		from libs.agent.react_controller import ReActController

		gemini_style = bool(getattr(self.args, "gemini_style", False))
		one_shot = bool(getattr(self, "INTERPRETER_PROMPT_FILE", False) and getattr(self.args, "file", None))
		# Keep a mutable holder so slash handlers can rebuild the controller.
		state = {"controller": None, "max_steps": max(int(getattr(self, "MAX_REPAIR_ATTEMPTS", 3) or 3), 10)}

		def _make_controller(model_name: str):
			return ReActController(
				model_name=model_name,
				api_key=None,
				unsafe_mode=self.UNSAFE_EXECUTION,
				log_path="logs/agent_react.jsonl",
				max_steps=state["max_steps"],
			)

		def _on_model_switched(name: str):
			state["controller"] = _make_controller(name)

		try:
			if gemini_style:
				self.console.print("[bold cyan]Gemini-style agentic REPL[/bold cyan] (ReAct · free LLMs)")
				self.console.print(
					f"Model: [bold]{self.INTERPRETER_MODEL}[/bold]  ·  "
					"Commands: /free  /model  /help  /exit"
				)
			else:
				self.console.print("[bold yellow]Running in ReAct Agentic Mode[/bold yellow]")
				if not one_shot:
					self.console.print("Commands: /free  /model  /help  /exit")

			state["controller"] = _make_controller(self.INTERPRETER_MODEL)

			file_task = None
			if one_shot:
				try:
					with open(self.args.file, "r", encoding="utf-8") as file:
						file_task = file.read()
				except Exception as exc:
					self.logger.error(f"Error reading prompt file: {exc}")
					return

			while True:
				if file_task is not None:
					task = file_task
					file_task = None
				else:
					task = self._safe_input("Enter your task: ", default="")

				raw = (task or "").strip()
				if not raw:
					self.console.print("Task cannot be empty.")
					if one_shot:
						return
					continue

				lower = raw.lower()
				if lower in ("/exit", "exit", "quit", "/quit"):
					self.console.print("Exiting agentic mode.")
					return
				if lower in ("/help", "help"):
					self.console.print(
						"Agentic commands:\n"
						"  /free           Free-catalog table + interactive picker\n"
						"  /model          Interactive model picker (TUI)\n"
						"  /model <name>   Switch to configs/<name>.json (e.g. gemini-2.5-flash)\n"
						"  /settings       Interactive settings (TUI)\n"
						"  /help           Show this help\n"
						"  /exit           Leave the agentic REPL\n"
						"Or type a natural-language task to plan/act/observe."
					)
					if one_shot:
						return
					continue
				if lower in ("/settings", "/mode"):
					setting = "settings" if lower == "/settings" else "mode"
					self._apply_runtime_settings(self._open_tui_settings(setting))
					if one_shot:
						return
					continue
				if lower == "/free":
					self._handle_free_slash_command(on_switched=_on_model_switched)
					if one_shot:
						return
					continue
				if lower == "/model" or lower.startswith("/model "):
					self._handle_model_slash_command(raw, on_switched=_on_model_switched)
					if one_shot:
						return
					continue
				# Unknown slash commands must not start a ReAct task
				if raw.startswith("/") and not raw.startswith("//"):
					cmd = raw.split(maxsplit=1)[0]
					self.console.print(
						f"[yellow]Unknown command:[/yellow] {cmd}. "
						"Try /help, /free, /model, or /exit."
					)
					if one_shot:
						return
					continue

				# Refuse traceback/error pastes (B4/B5).
				if is_non_task_input(raw):
					self.console.print(
						"[yellow]Tip:[/yellow] That looks like an error traceback, not a task. "
						"Please describe what you want me to do instead."
					)
					if one_shot:
						return
					continue

				state["controller"].run(raw)
				if one_shot:
					return
		except KeyboardInterrupt:
			self.console.print("\n[bold red]Agentic workflow interrupted by user.[/bold red]")

	def interpreter_main(self, version):
		return run_interpreter_main(self, version)
