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
from libs.safety_manager import ExecutionSafetyManager
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
		self.UNSAFE_EXECUTION = getattr(args, "unsafe", False)
		self.safety_manager = ExecutionSafetyManager(unsafe_mode=self.UNSAFE_EXECUTION)
		self.code_interpreter = CodeInterpreter(safety_manager=self.safety_manager)
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

	def _open_tui_settings(self, setting_type):
		return open_tui_settings(self, setting_type)

	def _apply_runtime_settings(self, settings):
		apply_runtime_settings(self, settings, display_fn=display_markdown_message, path_isfile=os.path.isfile)

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
		from libs.free_llms import FreeLLMCatalog
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
				"Commands: /free  /model <name>  /help  /exit"
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

			config = self.config_values or {}
			litellm_model = str(config.get("model") or self.INTERPRETER_MODEL)
			temperature = float(config.get("temperature", 0.2) or 0.2)
			max_tokens = int(config.get("max_tokens", 4096) or 4096)
			config_provider = str(config.get("provider") or config.get("config_provider") or "")
			api_base = str(config.get("api_base") or "")

			def completion_fn(model, messages, tools):
				from libs.llm_dispatcher import build_completion_kwargs

				# Prefer live config after /model switches
				cfg = self.config_values or {}
				active_model = str(cfg.get("model") or litellm_model)
				kwargs = build_completion_kwargs(
					model=active_model,
					messages=messages,
					temperature=float(cfg.get("temperature", temperature) or temperature),
					max_tokens=int(cfg.get("max_tokens", max_tokens) or max_tokens),
					config_provider=str(cfg.get("provider") or cfg.get("config_provider") or config_provider),
					api_base=str(cfg.get("api_base") or api_base),
				)
				kwargs["tools"] = tools
				kwargs["tool_choice"] = "auto"
				return litellm.completion(model=active_model, **kwargs)

			context_manager = ContextManager(token_limit=100_000, preserve_last_n=6)
			loop = AutonomousAgentLoop(
				model=litellm_model,
				auto_mode=auto_mode,
				registry=registry,
				completion_fn=completion_fn,
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
						"  /free           List free/cheap LLM presets\n"
						"  /model <name>   Switch model config for next run\n"
						"  /tools          List registered tools\n"
						"  /help           Show this help\n"
						"  /exit           Leave the autonomous REPL\n"
						"Or type a natural-language task to run the tool loop."
					)
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
					print(FreeLLMCatalog.load().format_table())
					if one_shot:
						return
					continue
				if lower.startswith("/model"):
					parts = raw.split(maxsplit=1)
					if len(parts) < 2 or not parts[1].strip():
						self.console.print("Usage: /model <config-name>")
					else:
						model = parts[1].strip()
						config_path = f"configs/{model}.json"
						if not os.path.exists(config_path):
							self.console.print(
								f"Model {model} does not exist. Use /free or /list (in --cli)."
							)
						else:
							self.INTERPRETER_MODEL = model
							self.INTERPRETER_MODEL_LABEL = model
							self.initialize_client()
							cfg = self.config_values or {}
							loop.model = str(cfg.get("model") or self.INTERPRETER_MODEL)
							self.console.print(f"Model switched to [bold]{model}[/bold]")
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
		from libs.free_llms import FreeLLMCatalog

		gemini_style = bool(getattr(self.args, "gemini_style", False))
		one_shot = bool(getattr(self, "INTERPRETER_PROMPT_FILE", False) and getattr(self.args, "file", None))

		try:
			if gemini_style:
				self.console.print("[bold cyan]Gemini-style agentic REPL[/bold cyan] (ReAct · free LLMs)")
				self.console.print(
					f"Model: [bold]{self.INTERPRETER_MODEL}[/bold]  ·  "
					"Commands: /free  /model <name>  /help  /exit"
				)
			else:
				self.console.print("[bold yellow]Running in ReAct Agentic Mode[/bold yellow]")
				if not one_shot:
					self.console.print("Commands: /free  /model <name>  /help  /exit")

			max_steps = max(int(getattr(self, "MAX_REPAIR_ATTEMPTS", 3) or 3), 10)
			controller = ReActController(
				model_name=self.INTERPRETER_MODEL,
				api_key=None,
				unsafe_mode=self.UNSAFE_EXECUTION,
				log_path="logs/agent_react.jsonl",
				max_steps=max_steps,
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
					self.console.print("Exiting agentic mode.")
					return
				if lower in ("/help", "help"):
					self.console.print(
						"Agentic commands:\n"
						"  /free           List free/cheap LLM presets\n"
						"  /model <name>   Switch model config for next ReAct run\n"
						"  /help           Show this help\n"
						"  /exit           Leave the agentic REPL\n"
						"Or type a natural-language task to plan/act/observe."
					)
					if one_shot:
						return
					continue
				if lower == "/free":
					print(FreeLLMCatalog.load().format_table())
					if one_shot:
						return
					continue
				if lower.startswith("/model"):
					parts = raw.split(maxsplit=1)
					if len(parts) < 2 or not parts[1].strip():
						self.console.print("Usage: /model <config-name>")
					else:
						model = parts[1].strip()
						config_path = f"configs/{model}.json"
						if not os.path.exists(config_path):
							self.console.print(
								f"Model {model} does not exist. Use /free or /list (in --cli)."
							)
						else:
							self.INTERPRETER_MODEL = model
							self.INTERPRETER_MODEL_LABEL = model
							controller = ReActController(
								model_name=model,
								api_key=None,
								unsafe_mode=self.UNSAFE_EXECUTION,
								log_path="logs/agent_react.jsonl",
								max_steps=max_steps,
							)
							self.console.print(f"Model switched to [bold]{model}[/bold]")
					if one_shot:
						return
					continue

				controller.run(raw)
				if one_shot:
					return
		except KeyboardInterrupt:
			self.console.print("\n[bold red]Agentic workflow interrupted by user.[/bold red]")

	def interpreter_main(self, version):
		return run_interpreter_main(self, version)
