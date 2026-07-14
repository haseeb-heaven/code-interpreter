"""Interactive REPL / main session loop for the Interpreter orchestrator."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

from libs.key_manager import AllKeysExhaustedError
from libs.logger import Logger


def run_interpreter_main(interp, version):
	"""Body of Interpreter.interpreter_main — pure behavior-preserving move."""
	# Resolve display helpers via interpreter_lib so test patches on
	# libs.interpreter_lib.display_* continue to work.
	from libs import interpreter_lib as ilib
	_display_markdown_message = ilib.display_markdown_message
	_display_code = ilib.display_code

	structured = bool(
		getattr(interp, "_structured_output_active", lambda: False)()
	)

	def display_markdown_message(message):
		if structured:
			return
		_display_markdown_message(message)

	def display_code(*args, **kwargs):
		if structured:
			return
		_display_code(*args, **kwargs)

	interp.interpreter_version = version
	interp.logger.info(f"Interpreter - v{interp.interpreter_version}")

	os_platform = interp.utility_manager.get_os_platform()
	os_name = os_platform[0]
	generated_output = None
	code_snippet = None
	code_output, code_error = None, None
	extracted_file_name = None 

	# Seting the mode.
	if interp.SCRIPT_MODE:
		interp.INTERPRETER_MODE = 'script'
	elif interp.COMMAND_MODE:
		interp.INTERPRETER_MODE = 'command'
	elif interp.VISION_MODE:
		interp.INTERPRETER_MODE = 'vision'
	elif interp.CHAT_MODE:
		interp.INTERPRETER_MODE = 'chat'

	start_sep = str(interp.config_values.get('start_sep', '```'))
	end_sep = str(interp.config_values.get('end_sep', '```'))

	interp.logger.info(f"Mode: {interp.INTERPRETER_MODE} Start separator: {start_sep}, End separator: {end_sep}")

	# Display system and Assistant information (skip in structured/piped modes).
	input_prompt_mode = "File" if interp.INTERPRETER_PROMPT_FILE else "Input"
	# Genuinely-interactive prompt-input REPL only — a `-f` prompt-file run is
	# one-shot (AGENTS.md), so the big banner would just be noise there.
	if not structured and not interp.INTERPRETER_PROMPT_FILE:
		try:
			from libs.agent.gemini_ui import render_persistent_banner

			render_persistent_banner(interp.console)
		except Exception as exc:
			interp.logger.debug(f"Persistent banner render failed: {exc}")
	if not structured:
		interp._display_session_banner(os_name, input_prompt_mode)
		display_markdown_message("Welcome to **Interpreter**, I'm here to **assist** you with your everyday tasks. ")

	# Main System and Assistant loop.
	running = True
	while running:
		try:
			task = None

			if interp.INTERPRETER_PROMPT_INPUT:
				interp.logger.info("Reading prompt from input.")
				# Main input prompt - System and Assistant.
				task = interp._safe_input("> ", default="/exit")
			elif interp.INTERPRETER_PROMPT_FILE:
				prompt_file_name = interp.args.file

				# Setting the prompt file path.
				if not prompt_file_name:
					prompt_file_name = 'prompt.txt'

				# Prefer explicit path if it exists; else legacy system/<name>; else cwd.
				candidates = []
				if os.path.isabs(prompt_file_name) or os.path.dirname(prompt_file_name):
					candidates.append(prompt_file_name)
				candidates.append(os.path.join(os.getcwd(), prompt_file_name))
				candidates.append(os.path.join(os.getcwd(), 'system', os.path.basename(prompt_file_name)))

				prompt_file_path = None
				for candidate in candidates:
					if os.path.exists(candidate):
						prompt_file_path = candidate
						break
				if prompt_file_path is None:
					prompt_file_path = candidates[-1]

				# check if the file exists.
				if not os.path.exists(prompt_file_path):
					interp.logger.error(f"Prompt file not found: {prompt_file_path}")
					if getattr(interp, "AUTO_YES", False):
						display_markdown_message(f"Prompt file not found: {prompt_file_path}")
						break
					user_confirmation = interp._safe_input("Create a new prompt file (Y/N)?: ", default="n")
					if user_confirmation.lower() == 'y':
						interp.logger.info("Creating new prompt file.")
						interp.utility_manager.create_file(prompt_file_path)
						display_markdown_message("New prompt file created **successfully** ")
					else:
						interp.logger.info("User declined to create new prompt file.")
						display_markdown_message("User declined to create new prompt file.\nSwitching to input mode.")
						# Switch to input mode.
						interp.INTERPRETER_PROMPT_INPUT = True
						interp.INTERPRETER_PROMPT_FILE = False

						continue
					continue

				display_markdown_message(f"\nEnter your task in the file **'{prompt_file_path}'**")

				# File mode command section.
				# Non-interactive (--yes / CI): auto-execute once, no human prompt.
				if getattr(interp, "AUTO_YES", False):
					prompt_confirmation = "y"
					interp.logger.info("AUTO_YES: executing prompt from file without confirmation.")
				else:
					prompt_confirmation = interp._safe_input("Execute the prompt (Y/N/P/C) (P = Prompt Mode,C = Command Mode)?: ", default="n")
				if prompt_confirmation.lower() == 'y':
					interp.logger.info("Executing prompt from file.")

					interp.logger.info(f"Executing prompt from file {prompt_file_path}")
					task = interp.utility_manager.read_file(prompt_file_path)
				elif prompt_confirmation.lower() == 'n':
					interp.logger.info("Waiting for user confirmation to execute prompt from file.")
					print("Waiting for user confirmation to execute prompt from file.")
					interp.utility_manager.clear_screen()
					continue
				elif prompt_confirmation.lower() == 'p':
					interp.INTERPRETER_PROMPT_INPUT = True
					interp.INTERPRETER_PROMPT_FILE = False
					interp.logger.info("Changing input mode to prompt from file.")
					interp.utility_manager.clear_screen()
					continue
				elif prompt_confirmation.lower() == 'c':
					interp.logger.info("Changing input mode to command from file.")
					task = interp._safe_input("> ", default="/exit")
				else:
					# Invalid input mode (0x000022)
					interp.logger.error("Invalid input mode.")
					interp.utility_manager.clear_screen()
					continue

			# EXIT - Command section.
			if task.lower() == '/exit':
				break

			# HELP - Command section.
			elif task.lower() == '/help':
				interp.utility_manager.display_help()
				continue

			# CLEAR - Command section.
			elif task.lower() == '/clear':
				interp.utility_manager.clear_screen()
				continue

			# VERSION - Command section.
			elif task.lower() == '/version':
				interp.utility_manager.display_version(interp.interpreter_version)
				continue

			# PROMPT - Command section.
			elif task.lower() == '/prompt':
				if interp.INTERPRETER_PROMPT_INPUT:
					interp.INTERPRETER_PROMPT_INPUT = False
					interp.INTERPRETER_PROMPT_FILE = True
					interp.logger.info("Input mode changed to File.")
				else:
					interp.INTERPRETER_PROMPT_INPUT = True
					interp.INTERPRETER_PROMPT_FILE = False
					interp.logger.info("Input mode changed to Prompt.")
				continue

			# HISTORY - Command section.
			elif task.lower() == '/history':
				interp.INTERPRETER_HISTORY = not interp.INTERPRETER_HISTORY
				display_markdown_message(f"History is {'enabled' if interp.INTERPRETER_HISTORY else 'disabled'}")
				continue

			# FILE ATTACH - Local file awareness (#221) + data session (#222)
			elif task.lower().startswith('/file ') or task.lower() == '/file':
				parts = task.split(maxsplit=1)
				if len(parts) < 2 or not parts[1].strip():
					display_markdown_message("Usage: `/file path/to/file.csv`")
					continue
				from libs.context.file_context import normalize_paths
				from libs.data.repl_data_commands import ensure_data_session

				path = parts[1].strip().strip('"').strip("'")
				interp._attached_files = getattr(interp, "_attached_files", []) or []
				for p in normalize_paths([path]):
					if p not in interp._attached_files:
						interp._attached_files.append(p)
				# Best-effort load into DataSession for analysis commands.
				try:
					ensure_data_session(interp).load_file(path)
				except Exception as exc:
					interp.logger.warning("DataSession load skipped: %s", exc)
				display_markdown_message(
					f"Attached `{path}`. Use `/files` to list or `/clear-files` to detach."
				)
				continue

			elif task.lower() in ('/files', '/list-files'):
				attached = getattr(interp, "_attached_files", []) or []
				if not attached:
					display_markdown_message("No files attached. Use `/file path` to attach.")
				else:
					from libs.context.file_context import build_file_context

					display_markdown_message(build_file_context(attached))
				continue

			elif task.lower() in ('/clear-files', '/clearfiles'):
				interp._attached_files = []
				try:
					from libs.data.repl_data_commands import ensure_data_session

					ensure_data_session(interp).clear()
				except Exception:
					pass
				display_markdown_message("Cleared all attached files.")
				continue

			# DATA ANALYSIS COMMANDS (#222 / #223)
			elif task.lower().startswith(
				(
					"/eda",
					"/charts",
					"/export",
					"/clean",
					"/sql",
					"/templates",
					"/chart-style",
					"/notebook",
					"/ml",
					"/output",
				)
			):
				from libs.data.repl_data_commands import handle_data_repl_command

				handle_data_repl_command(interp, task, display_markdown_message)
				continue

			# SESSION - Persistent sessions (#218)
			elif task.lower() == '/sessions' or task.lower().startswith('/session'):
				interp.handle_session_command(task)
				continue

			# IMAGE - Multimodal attach (#216)
			elif task.lower().startswith('/image'):
				parts = task.split(maxsplit=1)
				if len(parts) < 2 or not parts[1].strip():
					display_markdown_message("Usage: `/image <path-or-url>` then ask a question.")
					continue
				image_path = parts[1].strip().strip('"').strip("'")
				interp._pending_images = getattr(interp, '_pending_images', []) or []
				interp._pending_images.append(image_path)
				display_markdown_message(
					f"Image queued: `{image_path}`. Type your question about it (or another `/image`)."
				)
				question = interp._safe_input("💬 You: ", default="")
				if not (question or "").strip():
					display_markdown_message("No question provided; image kept for the next task.")
					continue
				from libs.vision.image_handler import is_vision_model

				model_label = str(getattr(interp, 'INTERPRETER_MODEL', '') or '')
				if not is_vision_model(model_label):
					display_markdown_message(
						f"WARNING: Model '{model_label}' may not support image inputs."
					)
				generated_output = interp._generate_content_with_retries(
					question.strip(),
					interp.history,
					config_values=interp.config_values,
					image_file=None,
				)
				display_markdown_message(f"{generated_output}")
				interp.emit_turn_result(result_text=str(generated_output or ""))
				continue

			# SEARCH - Web search (#217)
			elif task.lower().startswith('/search'):
				parts = task.split(maxsplit=1)
				if len(parts) < 2 or not parts[1].strip():
					display_markdown_message("Usage: `/search <query>`")
					continue
				query = parts[1].strip()
				from libs.key_manager import resolve_search_provider
				from libs.tools.web_search_tool import WebSearchTool

				provider, api_key = resolve_search_provider(
					cli_provider=getattr(interp.args, "search_provider", None),
					cli_api_key=getattr(interp.args, "search_api_key", None),
				)
				# Prefer registry tool if already enabled
				registry = getattr(interp, "tool_registry", None)
				if registry is not None and registry.get("web_search") is not None:
					result = registry.dispatch("web_search", {"query": query, "max_results": 5})
					print(result.output if result.success else (result.error or result.output))
				else:
					try:
						searcher = WebSearchTool(provider=provider, api_key=api_key)
					except ValueError as exc:
						display_markdown_message(f"Web search unavailable: {exc}")
						continue
					print(searcher.search(query))
				continue

			elif task.lower().startswith('/memory'):
				parts = task.split()
				sub = parts[1].lower() if len(parts) > 1 else 'show'
				memory = getattr(interp, 'memory', None)
				if not memory:
					display_markdown_message("Memory manager not available.")
					continue
				if sub == 'clear':
					memory.clear()
					display_markdown_message("Memory cleared.")
				elif sub == 'stats':
					stats = memory.stats()
					display_markdown_message(
						"Memory stats: "
						f"entries={stats['entry_count']}, "
						f"tokens={stats['total_tokens']}/{stats['max_tokens']}, "
						f"history_file={stats['history_file']}"
					)
				else:
					query = " ".join(parts[2:]) if len(parts) > 2 else ""
					context = memory.get_context(query)
					if not context:
						display_markdown_message("Memory is empty.")
					else:
						lines = []
						for entry in context:
							task_label = entry.get("task") or "memory"
							content = str(entry.get("content", "")).strip()
							lines.append(f"- **{task_label}**: {content}")
						display_markdown_message("Memory context:\n" + "\n".join(lines))
				continue

			# TOOLS - Command section.
			elif task.lower().startswith('/tools'):
				parts = task.split()
				registry = getattr(interp, 'tool_registry', None)
				if registry is None:
					print("No tools are registered.")
					continue
				if len(parts) == 2 and parts[1].lower() == 'list':
					print('Available tools:\n')
					for tool in registry.list_tools():
						print(f"{tool.get('name', '')} - {tool.get('description', '')}")
					print('', end='\n')
					continue
				if len(parts) == 3 and parts[1].lower() == 'info':
					tool = registry.get(parts[2])
					if tool is None:
						print(f"Unknown tool: {parts[2]}")
					else:
						print(json.dumps(tool.schema(), indent=2))
					continue
				print("Usage: /tools list | /tools info <name>")
				continue

			# SHELL - Command removed for security reasons.
			elif task.lower().startswith('/shell'):
				# The /shell feature has been intentionally removed. Inform the user.
				display_markdown_message("The '/shell' command has been removed for security reasons.")
				continue

			# add '/sandbox' command to toggle unsafe execution mode at runtime.
			elif task.lower() == '/sandbox':
				interp.toggle_sandbox_mode()
				continue

			elif task.lower().startswith('/audit'):
				from libs.security.audit_log import (
					audit_log_path,
					clear_audit,
					format_recent,
				)

				parts = task.split(None, 1)
				sub = parts[1].strip().lower() if len(parts) > 1 else ""
				if sub in ("", "show", "list"):
					print(format_recent(10))
				elif sub == "full":
					path = audit_log_path()
					if path.is_file():
						print(path.read_text(encoding="utf-8", errors="replace"))
					else:
						print(f"No audit log at {path}")
				elif sub == "clear":
					ok = clear_audit()
					print("Audit log cleared." if ok else "Failed to clear audit log.")
				else:
					print("Usage: /audit | /audit full | /audit clear")
				continue

			elif task.lower() == '/key-status':
				from libs.key_manager import KeyManager

				km = getattr(interp, "_key_manager", None) or KeyManager(config=interp.config_values or {})
				status = km.status()
				if not status:
					display_markdown_message("No API keys discovered. Add keys to `.env` (e.g. `OPENAI_API_KEY` or `OPENAI_API_KEY_1`).")
					continue
				print("\nKey status:\n")
				print(f"{'Provider':<14} {'Idx':<4} {'Key':<14} {'State':<10} {'Fail':<5} {'OK':<5} {'Avail':<6} {'Recovery ETA'}")
				for provider, rows in status.items():
					for row in rows:
						eta = ""
						now = time.time()
						until = max(float(row.get("rate_limited_until") or 0), float(row.get("circuit_open_until") or 0))
						if until > now:
							eta = time.strftime("%H:%M:%S", time.localtime(until))
						print(
							f"{provider:<14} {row['index']:<4} {row['masked']:<14} "
							f"{row['circuit_state']:<10} {row['failures']:<5} {row['successes']:<5} "
							f"{str(row['available']):<6} {eta}"
						)
				print()
				continue

			elif task.lower() == '/reload-keys':
				from libs.key_manager import KeyManager
				from dotenv import load_dotenv

				load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"), override=True)
				km = getattr(interp, "_key_manager", None) or KeyManager(config=interp.config_values or {})
				km.reload(config=interp.config_values or {})
				interp._key_manager = km
				display_markdown_message("API keys reloaded from `.env`.")
				continue

			elif task.lower() == '/metrics':
				from libs.key_manager import KeyManager, MetricsLogger

				km = getattr(interp, "_key_manager", None)
				metrics = km.metrics if km else MetricsLogger()
				summary = metrics.summary()
				print(f"\nLLM metrics (total={summary.get('total', 0)}):\n")
				print(f"{'Provider':<14} {'Reqs':<6} {'Success%':<10} {'Avg ms':<10} {'P95 ms':<10} {'RL':<5} {'CB'}")
				for provider, data in (summary.get("providers") or {}).items():
					print(
						f"{provider:<14} {data['requests']:<6} {data['success_rate']*100:>7.1f}%  "
						f"{data['avg_latency_ms']:<10.1f} {data['p95_latency_ms']:<10.1f} "
						f"{data['rate_limit_events']:<5} {data['circuit_open_events']}"
					)
				print()
				continue

			# LOG - Command section.
			elif task.lower() == '/debug':
				# Toggle the log level to Debug/Silent.
				logger_mode = Logger.get_current_level()

				if logger_mode.lower() == 'debug':
					Logger.set_level_to_error()
					display_markdown_message("**Debug** mode **disabled**")
				else:
					Logger.set_level_to_debug()
					display_markdown_message("**Debug** mode **enabled**")
				continue

			# LIST - Command section.
			elif task.lower() == '/list':
				# Get the models info
				configs_files = interp.utility_manager.list_available_models()

				# Printing the models info.
				print('Available models:\n')
				for index, model in enumerate(configs_files, 1):
					print(f'{index}. {model}')
				print('', end='\n')

				# Print all the available modes.
				print('Available modes:\n')
				for index, mode in enumerate(['code','script','command','vision','chat'], 1):
					print(f'{index}. {mode}',end='\n')

				# Print all the available languages.
				print('\nAvailable languages:\n')
				for index, language in enumerate(['python','javascript'], 1):
					print(f'{index}. {language}')

				continue

			# FREE - curated free/cheap LLM presets (Gemini-CLI-style model discovery)
			elif task.lower() == '/free':
				from libs.free_llms import FreeLLMCatalog

				print(FreeLLMCatalog.load().format_table())
				continue

			# UPGRAGE - Command section.
			elif task.lower() == '/upgrade':
				interp.utility_manager.upgrade_interpreter()
				continue

			# EXECUTE - Command section.
			elif task.lower() == '/execute':
				os_name = os_platform[0].lower()
				interp.execute_last_code(os_name)
				continue

			# SAVE - Command section.
			elif task.lower() == '/save':
				mode_type = interp.INTERPRETER_MODE
				latest_code_extension: str = ""

				# Get the OS platform.
				os_name = os_platform[0].lower()

				# Set the script or command extension based on the OS platform and mode type
				extensions = {
					"script": {
						"darwin": ".applescript",
						"linux": ".sh",
						"windows": ".bat"
					},
					"command": {
						"darwin": ".sh",
						"linux": ".sh",
						"windows": ".bat"
					},
					"code": lambda lang: '.py' if lang == 'python' else '.js'
				}

				lower_os_name = os_name.lower()
				if mode_type.lower() in extensions:
					if mode_type.lower() == "code":
						latest_code_extension = extensions["code"](interp.INTERPRETER_LANGUAGE)
					else:
						for key in extensions[mode_type.lower()]:
							if key in lower_os_name:
								latest_code_extension = extensions[mode_type.lower()][key]
								break
						else:
							raise ValueError(f"Unsupported operating system: {os_name}")
				else:
					raise ValueError(f"Unsupported mode type: {mode_type}")

				latest_code_name = f"output/{mode_type}_{time.strftime('%Y_%m_%d-%H_%M_%S', time.localtime())}" + latest_code_extension
				latest_code = code_snippet
				interp.code_interpreter.save_code(latest_code_name, latest_code)
				display_markdown_message(f"{mode_type.capitalize()} saved successfully to **{latest_code_name}**")
				continue

			# EDIT - Command section.
			elif task.lower() == '/edit':
				# Get the OS platform.
				os_name = os_platform[0].lower()

				code_file, code_snippet = interp.utility_manager.get_output_history(mode=interp.INTERPRETER_MODE, os_name=os_name, language=interp.INTERPRETER_LANGUAGE)

				# check if the code is empty
				if code_snippet is None or code_file is None:
					interp.logger.error("Code history or file is empty.")
					display_markdown_message("Code history or file is empty. - Please use **-s** flag or **/save** command to save the code.")
					continue

				# Attempt to open with default editor.
				interp.logger.info(f"Opening code in default editor for os '{os_platform}'")
				try:
					if 'darwin' in os_name:
						subprocess.call(['open', code_file.name if not isinstance(code_file, str) else code_file])
					elif 'linux' in os_name:
						subprocess.call(['xdg-open', code_file.name if not isinstance(code_file, str) else code_file])
					elif 'windows' in os_name:
						os.startfile(code_file.name if not isinstance(code_file, str) else code_file)
					continue
				except Exception:
					interp.logger.warning("Default editor not found. Trying vim...")
					# Check if vim is available
					if shutil.which('vim'):
						interp.logger.info(f"Opening code in vim editor {code_file.name if not isinstance(code_file, str) else code_file}")
						subprocess.call(['vim', code_file.name if not isinstance(code_file, str) else code_file])
						continue
					else:
						interp.logger.error("No suitable editor found.")
						continue

			# FIX - Command section.
			elif task.lower() == '/fix':

				if not code_error:
					code_error = code_output

				if not code_error:
					display_markdown_message("Error: No error found in the code to fix.")
					continue

				fix_prompt = f"Fix the errors in {interp.INTERPRETER_LANGUAGE} language.\nCode is \n'{code_snippet}'\nAnd Error is \n'{code_error}'\n"
				"give me output only in code and no other text or explanation. And comment in code where you fixed the error.\n"

				# Start the LLM Request.
				interp.logger.info(f"Fix Prompt: {fix_prompt}")
				from libs.vision.image_handler import image_file_arg_for_path

				generated_output = interp._generate_content_with_retries(
					fix_prompt,
					interp.history,
					config_values=interp.config_values,
					image_file=image_file_arg_for_path(extracted_file_name),
				)

				# Extract the code from the generated output.
				interp.logger.info(f"Generated output type {type(generated_output)}")
				code_snippet = interp.code_interpreter.extract_code(generated_output, start_sep, end_sep)

				# Display the extracted code.
				if code_snippet:
					interp.logger.info(f"Extracted code: {code_snippet[:50]}")

					if interp.DISPLAY_CODE:
						interp.logger.info("Code extracted successfully.")

						# Execute the code if the user has selected.
						code_output, code_error = interp.execute_code(code_snippet, interp.INTERPRETER_LANGUAGE)

						if code_output:
							interp.logger.info(f"{interp.INTERPRETER_LANGUAGE} code executed successfully.")
							display_code(code_output)
							interp.logger.info(f"Output: {code_output[:100]}")
						elif code_error:
							interp.logger.info(f"{interp.INTERPRETER_LANGUAGE} code executed with error.")
							display_markdown_message(f"Error: {code_error}")
				continue

			# MODE - Command section.
			elif task.lower() == '/settings':
				interp._ensure_terminal_ui()
				interp._apply_runtime_settings(interp._open_tui_settings("settings"))
				display_markdown_message("Settings updated.")
				continue

			elif task.lower() == '/mode':
				interp._ensure_terminal_ui()
				interp._apply_runtime_settings(interp._open_tui_settings("mode"))
				display_markdown_message(f"Mode changed to '{interp.INTERPRETER_MODE}'")
				continue

			elif any(command in task.lower() for command in ['/mode ']):
				mode = task.split(' ')[1]
				if mode:
					if mode.lower() not in ['code','script','command','vision','chat']:
						mode = 'code'
						display_markdown_message(f"The input mode is not supported. Mode changed to {mode},"
												 "\nUse '/list' command to get the list of supported modes.")
					else:
						interp._apply_mode(mode)
						display_markdown_message(f"Mode changed to '{interp.INTERPRETER_MODE}'")
				continue

			# MODEL - Command section.
			elif task.lower() == '/model':
				# Always open TUI picker (works under --cli via lazy TerminalUI).
				if hasattr(interp, "_handle_model_slash_command"):
					interp._handle_model_slash_command(task)
				else:
					interp._ensure_terminal_ui()
					interp._apply_runtime_settings(interp._open_tui_settings("model"))
				display_markdown_message(f"Model changed to '{interp.INTERPRETER_MODEL_LABEL}'")
				continue

			elif any(command in task.lower() for command in ['/model ']):
				model = task.split(' ')[1]
				if model:
					from libs.free_llms import resolve_model_config_name

					resolved = resolve_model_config_name(model)
					if not resolved:
						display_markdown_message(
							f"Model {model} does not exists. Opening model picker…"
						)
						if hasattr(interp, "_handle_model_slash_command"):
							interp._handle_model_slash_command("/model")
						else:
							interp._ensure_terminal_ui()
							interp._apply_runtime_settings(interp._open_tui_settings("model"))
						continue
					else:
						interp.INTERPRETER_MODEL = resolved
						interp.INTERPRETER_MODEL_LABEL = resolved
						display_markdown_message(f"Model changed to '{interp.INTERPRETER_MODEL}'")
						interp.initialize_client()  # Reinitialize the client with new model.
				continue

			# LANGUAGE - Command section.
			elif task.lower() in ['/language', '/lang']:
				interp._ensure_terminal_ui()
				interp._apply_runtime_settings(interp._open_tui_settings("language"))
				display_markdown_message(f"Language changed to '{interp.INTERPRETER_LANGUAGE}'")
				continue

			elif any(command in task.lower() for command in ['/language','/lang']):
				split_task = task.split(' ')
				if len(split_task) > 1:
					language = split_task[1]
					if language:
						interp.INTERPRETER_LANGUAGE = language
						if language not in ['python', 'javascript']:
							interp.INTERPRETER_LANGUAGE = 'python'
							display_markdown_message(f"The input language is not supported. Language changed to {interp.INTERPRETER_LANGUAGE}")
						display_markdown_message(f"Language changed to '{interp.INTERPRETER_LANGUAGE}'")
				continue

			# INSTALL - Command section.
			elif task.lower().startswith('/install'):
				parts = task.split(' ')
				if len(parts) >= 3:
					# Case: /install <language> <package>
					language = parts[1].lower()
					package_name = parts[2]

					# Validate language
					if language in ['python', 'py']:
						language = 'python'
					elif language in ['javascript', 'js', 'node']:
						language = 'javascript'
					else:
						# If unknown language, treat as package name to be safe
						package_name = parts[1]
						language = interp.INTERPRETER_LANGUAGE
				elif len(parts) == 2:
					package_name = parts[1]
					language = interp.INTERPRETER_LANGUAGE
				else:
					display_markdown_message("Usage: **/install [language] <package_name>**")
					continue

				# check if package name is not system module.
				system_modules = interp.package_manager.get_system_modules()

				if package_name in system_modules:
					interp.logger.info(f"Package {package_name} is a system module.")
					display_markdown_message(f"Package {package_name} is a system module.")
					continue

				if package_name:
					interp.logger.info(f"Installing package {package_name} for {language}")
					display_markdown_message(f"Installing package **{package_name}** for **{language}**...")
					try:
						interp.package_manager.install_package(package_name, language)
						display_markdown_message(f"Successfully installed **{package_name}**")
					except Exception as ex:
						interp.logger.error(f"Manual installation failed: {ex}")
						display_markdown_message(f"Failed to install **{package_name}**: {ex}")
				continue

			# Get the prompt based on the mode.
			else:
				# Multi-agent pipeline path (--agent)
				if getattr(interp, "AGENT_MODE", False):
					from libs.context.file_context import inject_file_context

					task = inject_file_context(task, getattr(interp, "_attached_files", None))
					display_markdown_message("**Agent pipeline** running: IntentRouter → Planner → SafetyGuard → Executor → Repairer → Verifier → Reviewer")
					agent_ctx = interp.run_agent_pipeline(task, os_name)
					code_snippet = agent_ctx.code or None
					code_output = agent_ctx.output or None
					code_error = agent_ctx.error or None
					display_markdown_message(
						f"Intent=`{agent_ctx.intent}` | safe=`{agent_ctx.safe}` | "
						f"verified=`{agent_ctx.verified}` | approved=`{agent_ctx.approved}`"
					)
					if agent_ctx.plan:
						display_markdown_message("**Plan:** " + " → ".join(str(s) for s in agent_ctx.plan))
					if agent_ctx.code:
						display_code(agent_ctx.code, language=interp.INTERPRETER_LANGUAGE)
					if agent_ctx.output:
						display_code(agent_ctx.output)
					if agent_ctx.error:
						display_markdown_message(f"Error: {agent_ctx.error}")
					reason = agent_ctx.metadata.get("review_reason") or agent_ctx.metadata.get("verify_reason")
					if reason:
						display_markdown_message(f"Review: {reason}")
					interp.emit_turn_result(
						result_text=reason or (agent_ctx.output or "") or "",
						code=code_snippet,
						execution_output=code_output,
						error=code_error,
						status="error" if code_error else "success",
					)
					interp.history_manager.save_history_json(
						task, interp.INTERPRETER_MODE, os_name, interp.INTERPRETER_LANGUAGE,
						task, code_snippet, code_output, interp.INTERPRETER_MODEL,
					)
					interp.record_session_turn(
						task=task,
						prompt=task,
						code_snippet=code_snippet,
						code_output=code_output,
						code_error=code_error,
						os_name=os_name,
					)
					# Non-interactive file runs are one-shot (CI / scripts).
					if getattr(interp, "AUTO_YES", False) and interp.INTERPRETER_PROMPT_FILE:
						break
					continue

				prompt = interp.get_mode_prompt(task, os_name)
				# Inject attached file context (#221) after mode prompt so absolute paths stick.
				attached = getattr(interp, "_attached_files", None) or []
				if attached:
					from libs.context.file_context import build_file_context

					ctx = build_file_context(attached)
					if ctx:
						prompt = f"{ctx}\n\n{prompt}"
				# Inject DataSession schema memory (#222)
				data_session = getattr(interp, "data_session", None)
				if data_session is not None:
					block = data_session.context_block()
					if block:
						prompt = f"{block}\n\n{prompt}"
					if getattr(data_session, "chart_style", "") == "plotly" or getattr(
						interp.args, "interactive_charts", False
					):
						from libs.output.plotly_manager import plotly_system_hint

						prompt = f"{plotly_system_hint()}\n\n{prompt}"
				# Science prompt layer (#223)
				from libs.prompts.science_prompt import science_prompt_block

				sci = science_prompt_block(
					force=bool(getattr(interp.args, "science", False)),
					task=task,
				)
				if sci:
					prompt = f"{sci}\n\n{prompt}"
				interp.logger.info(f"Prompt init is '{prompt}'")

				# Check if the prompt is empty.
				if not prompt:
					display_markdown_message("Please **enter** a valid task.")
					continue

			# Clean the responses
			interp.utility_manager._clean_responses()

			# Print Model and Mode information.
			interp.logger.info(f"Interpreter Mode: {interp.INTERPRETER_MODE} Model: {interp.INTERPRETER_MODEL}")

			# Check if prompt contains any file uploaded by user.
			extracted_file_name = interp.utility_manager.extract_file_name(prompt)
			interp.logger.info(f"Input prompt file name: '{extracted_file_name}'")

			try:
				if hasattr(interp, "safety_manager") and interp.safety_manager:
					interp.safety_manager.set_user_intent_paths(f"{task}\n{prompt}")
			except Exception as intent_exc:
				interp.logger.debug(f"user-intent path setup skipped: {intent_exc}")

			if extracted_file_name is not None:
				full_path = interp.utility_manager.get_full_file_path(extracted_file_name)
				interp.logger.info(f"Input prompt full_path: '{full_path}'")

				# Check if image contains URL.
				if 'http' in extracted_file_name or 'https' in extracted_file_name or 'www.' in extracted_file_name:
					interp.logger.info("Image contains URL Skipping the file processing.")

				else:
					# Check if the file exists and is a file
					if os.path.isfile(full_path):
						# Check if file size is less than 50 KB
						file_size_max = 50000
						file_size = os.path.getsize(full_path)
						interp.logger.info(f"Input prompt file_size: '{file_size}'")
						if file_size < file_size_max:
							try:
								with open(full_path, 'r', encoding='utf-8') as file:
									# Check if file extension is .json, .csv, or .xml
									file_extension = os.path.splitext(full_path)[1].lower()

									if file_extension in ['.json','.xml']:
										# Split by new line and read only 20 lines
										file_data = '\n'.join(file.readline() for _ in range(20))
										interp.logger.info(f"Input prompt JSON/XML file_data: '{str(file_data)}'")

									elif file_extension == '.csv':
										# Read only headers of the csv file
										file_data = interp.utility_manager.read_csv_headers(full_path)
										interp.logger.info(f"Input prompt CSV file_data: '{str(file_data)}'")

									else:
										file_data = file.read()
										interp.logger.info(f"Input prompt file_data: '{str(file_data)}'")

									task_lower = task.lower()
									if any(word in task_lower for word in ['graph', 'graphs', 'chart', 'charts']):
										prompt += "\n" + "This is file data from user input: " + str(file_data) + " use this to analyze the data."
										interp.logger.info(f"Input Prompt: '{prompt}'")
									else:
										interp.logger.info("The prompt does not contain both 'graph' and 'chart'.")
							except Exception as exception:
								interp.logger.error(f"Error reading file: {exception}")
						else:
							interp.logger.warning("File size is greater.")
					else:
						interp.logger.error("File does not exist or is not a file.")                         
			else:
				interp.logger.info("No file name found in the prompt.")

			# If graph/chart/table were requested, nudge the model toward a
			# default library + output filename -- but only when the task
			# hasn't already pinned those choices itself. A fully-specified
			# task ("...with matplotlib Agg, save PNG to <path>...") that
			# still gets told to use Plotly and 'chart.png' receives two
			# contradictory instructions, which measurably confuses smaller
			# models into never completing the task (#stability-fixes).
			task_lower = task.lower()
			output_already_specified = any(
				ext in task_lower for ext in ('.png', '.jpg', '.jpeg', '.svg', '.html', '.md')
			)
			library_already_specified = any(
				lib in task_lower
				for lib in (
					'matplotlib', 'plotly', 'seaborn', 'bokeh', 'altair',
					'chart.js', 'chartjs', 'pandas', 'datatables',
				)
			)
			hint_already_covered = output_already_specified or library_already_specified

			if not hint_already_covered and any(word in task_lower for word in ['graph', 'graphs']):
				if interp.INTERPRETER_LANGUAGE == 'python':
					prompt += "\n" + "using Python use Matplotlib save the graph in file called 'graph.png'"
				elif interp.INTERPRETER_LANGUAGE == 'javascript':
					prompt += "\n" + "using JavaScript use Chart.js save the graph in file called 'graph.png'"

			# if Chart were requested
			if not hint_already_covered and any(word in task_lower for word in ['chart', 'charts', 'plot', 'plots']):
				if interp.INTERPRETER_LANGUAGE == 'python':
					prompt += "\n" + "using Python use Plotly save the chart in file called 'chart.png'"
				elif interp.INTERPRETER_LANGUAGE == 'javascript':
					prompt += "\n" + "using JavaScript use Chart.js save the chart in file called 'chart.png'"

			# if Table were requested
			if not hint_already_covered and 'table' in task_lower:
				if interp.INTERPRETER_LANGUAGE == 'python':
					prompt += "\n" + "using Python use Pandas save the table in file called 'table.md'"
				elif interp.INTERPRETER_LANGUAGE == 'javascript':
					prompt += "\n" + "using JavaScript use DataTables save the table in file called 'table.html'"

			# If --search was requested (#217), this classic one-shot flow has
			# no function-calling loop to let the model invoke the web_search
			# tool itself (unlike the agentic auto-loop), so pre-fetch results
			# and inject them into the prompt before the LLM request.
			if getattr(interp.args, "search", False):
				import re

				from libs.key_manager import resolve_search_provider
				from libs.tools.web_search_tool import WebSearchTool

				quoted = re.search(r"['\"]([^'\"]+)['\"]", task)
				search_query = quoted.group(1) if quoted else task
				soft_fail_prefixes = (
					"duckduckgo-search not installed",
					"requests not installed",
					"search failed:",
					"unknown search provider",
				)
				try:
					provider, api_key = resolve_search_provider(
						cli_provider=getattr(interp.args, "search_provider", None),
						cli_api_key=getattr(interp.args, "search_api_key", None),
					)
					searcher = WebSearchTool(provider=provider, api_key=api_key)
					search_results = searcher.search(search_query)
					interp.logger.info(f"Web search for {search_query!r} via {provider}: {search_results[:200]}")
					if search_results.lower().startswith(soft_fail_prefixes):
						prompt += (
							"\n\nWeb search was requested but is unavailable in this "
							f"environment ({search_results}). If the task allows it, "
							"say so instead of guessing."
						)
					else:
						prompt += (
							"\n\nLive web search results for "
							f"'{search_query}' (already fetched, use them):\n{search_results}"
						)
				except Exception as search_exc:
					interp.logger.warning(f"Web search unavailable: {search_exc}")
					prompt += (
						"\n\nWeb search was requested but is unavailable in this "
						f"environment ({search_exc}). If the task allows it, say so "
						"instead of guessing."
					)

			# Start the LLM Request.
			interp.logger.info(f"Prompt: {prompt}")

			# Add relevance-based memory context.
			if interp.INTERPRETER_HISTORY and interp.INTERPRETER_MODE in ['chat', 'code']:
				memory = getattr(interp, 'memory', None)
				interp.history = memory.get_context(task) if memory else []

			from libs.vision.image_handler import image_file_arg_for_path

			generated_output = interp._generate_content_with_retries(
				prompt,
				interp.history,
				config_values=interp.config_values,
				image_file=image_file_arg_for_path(extracted_file_name),
			)

			# No extra processing for Vision mode / chat (avoid double-print when streamed).
			if interp.INTERPRETER_MODE in ['vision', 'chat']:
				if not getattr(interp, '_last_response_was_streamed', False):
					display_markdown_message(f"{generated_output}")
				interp._last_response_was_streamed = False
				interp.emit_turn_result(result_text=str(generated_output or ""))
				interp.record_session_turn(
					task=task,
					prompt=prompt,
					code_snippet=None,
					code_output=str(generated_output or ""),
					os_name=os_name,
				)
				# Non-interactive file runs are one-shot (CI / scripts).
				if getattr(interp, "AUTO_YES", False) and interp.INTERPRETER_PROMPT_FILE:
					break
				continue

			# Extract the code from the generated output.
			interp.logger.info(f"Generated output type {type(generated_output)}")
			code_snippet = interp.code_interpreter.extract_code(generated_output, start_sep, end_sep)
			code_snippet = interp._maybe_simplify_generated_code(task, code_snippet)
			display_language = interp.INTERPRETER_LANGUAGE if interp.CODE_MODE else 'bash'

			# Display the extracted code.
			if code_snippet:
				interp.logger.info(f"Extracted code: {code_snippet[:50]}")

			should_display_code = bool(code_snippet) and (
				interp.DISPLAY_CODE or (interp.INTERPRETER_PROMPT_INPUT and not interp.SAVE_CODE and not interp.EXECUTE_CODE)
			)
			if should_display_code:
				display_code(code_snippet, language=display_language)
				interp.logger.info("Code extracted successfully.")
			elif not code_snippet:
				if generated_output:
					if interp.INTERPRETER_MODE in ['code', 'script', 'command']:
						display_code(generated_output, language=display_language)
					else:
						display_markdown_message(f"{generated_output}")
					display_markdown_message("No executable code block was returned, so the raw model response is shown above.")
				else:
					display_markdown_message("The model returned an empty response.")

			if code_snippet:
				current_time = time.strftime("%Y_%m_%d-%H_%M_%S", time.localtime())

				if interp.INTERPRETER_LANGUAGE == 'javascript' and interp.SAVE_CODE and interp.CODE_MODE:
					interp.code_interpreter.save_code(f"output/code_{current_time}.js", code_snippet)
					interp.logger.info("JavaScript code saved successfully.")

				elif interp.INTERPRETER_LANGUAGE == 'python' and interp.SAVE_CODE and interp.CODE_MODE:
					interp.code_interpreter.save_code(f"output/code_{current_time}.py", code_snippet)
					interp.logger.info(f"{interp.INTERPRETER_LANGUAGE} code saved successfully.")

				elif interp.SAVE_CODE and interp.COMMAND_MODE:
					interp.code_interpreter.save_code(f"output/command_{current_time}.txt", code_snippet)
					interp.logger.info("Command saved successfully.")

				elif interp.SAVE_CODE and interp.SCRIPT_MODE:
					interp.code_interpreter.save_code(f"output/script_{current_time}.txt", code_snippet)
					interp.logger.info("Script saved successfully.")

				# Execute the code if the user has selected.
				code_output, code_error, sandbox_context = interp._execute_generated_output(code_snippet, interp.INTERPRETER_LANGUAGE)

				if code_output:
					interp.logger.info(f"{interp.INTERPRETER_LANGUAGE} code executed successfully.")
					display_code(code_output)
					interp.logger.info(f"Output: {code_output[:100]}")
				elif code_error and code_error.startswith("Safety blocked:"):
					interp.logger.warning(code_error)
					display_markdown_message(f"⚠️ **SAFETY BLOCKED**: {code_error}")
				elif code_error:
					interp.logger.info(f"{interp.INTERPRETER_LANGUAGE} code executed with error.")
					display_markdown_message(f"Error: {code_error}")
				else:
					if interp._last_execution_approved:
						display_markdown_message("Execution completed successfully.")

				# install Package on error.
				error_messages = ["ModuleNotFound", "ImportError", "No module named", "Cannot find module"]
				if code_error is not None and any(error_message in code_error for error_message in error_messages):
					package_name = interp.package_manager.extract_package_name(code_error, interp.INTERPRETER_LANGUAGE)

					# check if package name is not system module.
					system_modules = interp.package_manager.get_system_modules()

					# Skip installing system modules.
					if package_name in system_modules:
						interp.logger.info(f"Package {package_name} is a system module.")
						display_markdown_message(f"Package {package_name} is a system module.")
						raise Exception(f"Package {package_name} is a system module.")

					MAX_INSTALL_ATTEMPTS:int = 3
					if package_name:
						for attempt in range(1, MAX_INSTALL_ATTEMPTS + 1):
							try:
								interp.logger.info(f"Installing package {package_name} on interpreter {interp.INTERPRETER_LANGUAGE} (Attempt {attempt}/3)")
								interp.package_manager.install_package(package_name, interp.INTERPRETER_LANGUAGE)

								# Wait and Execute the code again.
								time.sleep(3)
								code_output, code_error, retry_sandbox = interp._execute_generated_output(code_snippet, interp.INTERPRETER_LANGUAGE, force_execute=True)
								if retry_sandbox:
									interp.safety_manager.cleanup_sandbox_context(retry_sandbox)
								if code_output:
									interp.logger.info(f"{interp.INTERPRETER_LANGUAGE} code executed successfully.")
									display_code(code_output)
									interp.logger.info(f"Output: {code_output[:100]}")
								elif code_error:
									interp.logger.info(f"{interp.INTERPRETER_LANGUAGE} code executed with error.")
									display_markdown_message(f"Error: {code_error}")
								else:
									display_markdown_message("Execution completed successfully.")
								break  # Exit retry loop on success
							except Exception as ex:
								if attempt < 3:
									interp.logger.warning(f"Attempt {attempt} to install package {package_name} failed: {ex}")
									display_markdown_message(f"Attempt {attempt}/3 to install package **{package_name}** failed. Retrying in 2 seconds...")
									time.sleep(2)
								else:
									interp.logger.error(f"Failed to install package {package_name} after 3 attempts: {ex}")
									display_markdown_message(f"Failed to install package **{package_name}** after 3 attempts. Error: {ex}. Proceeding with repair logic...")

				if code_error and not code_error.startswith("Safety blocked:"):
					code_snippet, repaired_output, repaired_error = interp._attempt_repair_after_failure(
						task,
						prompt,
						code_snippet,
						code_error,
						os_name,
						start_sep,
						end_sep,
						extracted_file_name,
						code_output=code_output,
					)
					if repaired_output:
						code_output = repaired_output
						code_error = repaired_error
						display_code(repaired_output)
					elif repaired_error and repaired_error != code_error:
						code_error = repaired_error
						display_markdown_message(f"Error: {repaired_error}")

				try:
					# Check if graph.png exists and open it.
					interp.utility_manager._open_resource_file('graph.png')

					# Check if chart.png exists and open it.
					interp.utility_manager._open_resource_file('chart.png')

					# Check if table.md exists and open it.
					interp.utility_manager._open_resource_file('table.md')
				except Exception as exception:
					display_markdown_message(f"Error in opening resource files: {str(exception)}")
				finally:
					# Cleanup sandbox after accessing artifacts
					if sandbox_context:
						interp.safety_manager.cleanup_sandbox_context(sandbox_context)

			interp.history_manager.save_history_json(task, interp.INTERPRETER_MODE, os_name, interp.INTERPRETER_LANGUAGE, prompt, code_snippet,code_output, interp.INTERPRETER_MODEL)

			# Structured output for scripting / piping (#219).
			interp.emit_turn_result(
				result_text=str(generated_output or ""),
				code=code_snippet,
				execution_output=code_output,
				error=code_error,
				status="error" if code_error else "success",
			)
			interp.record_session_turn(
				task=task,
				prompt=prompt,
				code_snippet=code_snippet,
				code_output=code_output,
				code_error=code_error,
				os_name=os_name,
			)

			# Non-interactive file runs are one-shot (CI / scripts).
			if getattr(interp, "AUTO_YES", False) and interp.INTERPRETER_PROMPT_FILE:
				break

		except Exception as exception:
			if isinstance(exception, AllKeysExhaustedError):
				provider = exception.provider or "the configured provider"
				eta = exception.earliest_recovery_ts
				eta_str = (
					time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(eta))
					if eta is not None
					else "unknown"
				)
				interp.logger.warning(
					f"All keys exhausted for provider '{provider}'. Earliest recovery: {eta_str}"
				)
				display_markdown_message(
					f"**All API keys for `{provider}` are currently exhausted.** Earliest recovery: `{eta_str}`."
				)
				display_markdown_message(
					"Try `/model <name>` to switch providers, or re-run with `--free` to "
					"auto-fallback to a free model next time."
				)
				# Non-interactive file runs are one-shot (CI / scripts) — without
				# this, a persistent exhausted-quota state re-reads the same
				# prompt file and re-raises the same error forever, spinning
				# until the external process timeout kills it (#stability-fixes).
				if getattr(interp, "AUTO_YES", False) and interp.INTERPRETER_PROMPT_FILE:
					break
				continue
			error_text = str(exception)
			if interp._is_recoverable_runtime_error(error_text):
				interp.logger.warning(f"Recoverable interpreter error: {error_text}")
				display_markdown_message(f"Request failed: {interp._format_runtime_error_message(error_text)}")
				display_markdown_message("Try `/model <name>` to switch models or `/list` to see the available options.")
				# Non-interactive file runs are one-shot (CI / scripts) — see
				# comment above; avoid an infinite retry loop on a persistent
				# recoverable error against the same prompt file.
				if getattr(interp, "AUTO_YES", False) and interp.INTERPRETER_PROMPT_FILE:
					break
				continue
			interp.logger.error(f"An error occurred in interpreter_lib: {error_text}")
			raise
