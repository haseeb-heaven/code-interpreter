"""Interactive REPL / main session loop for the Interpreter orchestrator."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

from libs.logger import Logger


def run_interpreter_main(interp, version):
	"""Body of Interpreter.interpreter_main — pure behavior-preserving move."""
	# Resolve display helpers via interpreter_lib so test patches on
	# libs.interpreter_lib.display_* continue to work.
	from libs import interpreter_lib as ilib
	display_markdown_message = ilib.display_markdown_message
	display_code = ilib.display_code


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

	# Display system and Assistant information.
	input_prompt_mode = "File" if interp.INTERPRETER_PROMPT_FILE else "Input"
	interp._display_session_banner(os_name, input_prompt_mode)

	# Display the welcome message.
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

				prompt_file_path = os.path.join(os.getcwd(), 'system', prompt_file_name)

				# check if the file exists.
				if not os.path.exists(prompt_file_path):
					interp.logger.error(f"Prompt file not found: {prompt_file_path}")
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
				generated_output = interp._generate_content_with_retries(fix_prompt, interp.history, config_values=interp.config_values, image_file=extracted_file_name)

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
			elif task.lower() == '/settings' and interp.terminal_ui:
				interp._apply_runtime_settings(interp._open_tui_settings("settings"))
				display_markdown_message("Settings updated.")
				continue

			elif task.lower() == '/mode' and interp.terminal_ui:
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
			elif task.lower() == '/model' and interp.terminal_ui:
				interp._apply_runtime_settings(interp._open_tui_settings("model"))
				display_markdown_message(f"Model changed to '{interp.INTERPRETER_MODEL_LABEL}'")
				continue

			elif any(command in task.lower() for command in ['/model ']):
				model = task.split(' ')[1]
				if model:
					model_config_file = f"configs/{model}.config"
					if not os.path.isfile(model_config_file):
						display_markdown_message(f"Model {model} does not exists. Please check the model name using '/list' command.")
						continue
					else:
						interp.INTERPRETER_MODEL = model
						interp.INTERPRETER_MODEL_LABEL = model
						display_markdown_message(f"Model changed to '{interp.INTERPRETER_MODEL}'")
						interp.initialize_client()  # Reinitialize the client with new model.
				continue

			# LANGUAGE - Command section.
			elif task.lower() in ['/language', '/lang'] and interp.terminal_ui:
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
					interp.history_manager.save_history_json(
						task, interp.INTERPRETER_MODE, os_name, interp.INTERPRETER_LANGUAGE,
						task, code_snippet, code_output, interp.INTERPRETER_MODEL,
					)
					continue

				prompt = interp.get_mode_prompt(task, os_name)
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

			# If graph were requested.
			task_lower = task.lower()
			if any(word in task_lower for word in ['graph', 'graphs']):
				if interp.INTERPRETER_LANGUAGE == 'python':
					prompt += "\n" + "using Python use Matplotlib save the graph in file called 'graph.png'"
				elif interp.INTERPRETER_LANGUAGE == 'javascript':
					prompt += "\n" + "using JavaScript use Chart.js save the graph in file called 'graph.png'"

			# if Chart were requested
			if any(word in task_lower for word in ['chart', 'charts', 'plot', 'plots']):    
				if interp.INTERPRETER_LANGUAGE == 'python':
					prompt += "\n" + "using Python use Plotly save the chart in file called 'chart.png'"
				elif interp.INTERPRETER_LANGUAGE == 'javascript':
					prompt += "\n" + "using JavaScript use Chart.js save the chart in file called 'chart.png'"

			# if Table were requested
			if 'table' in task_lower:
				if interp.INTERPRETER_LANGUAGE == 'python':
					prompt += "\n" + "using Python use Pandas save the table in file called 'table.md'"
				elif interp.INTERPRETER_LANGUAGE == 'javascript':
					prompt += "\n" + "using JavaScript use DataTables save the table in file called 'table.html'"

			# Start the LLM Request.     
			interp.logger.info(f"Prompt: {prompt}")

			# Add relevance-based memory context.
			if interp.INTERPRETER_HISTORY and interp.INTERPRETER_MODE in ['chat', 'code']:
				memory = getattr(interp, 'memory', None)
				interp.history = memory.get_context(task) if memory else []

			generated_output = interp._generate_content_with_retries(prompt, interp.history, config_values=interp.config_values,image_file=extracted_file_name)

			# No extra processing for Vision mode.
			if interp.INTERPRETER_MODE in ['vision', 'chat']:
				display_markdown_message(f"{generated_output}")
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

		except Exception as exception:
			error_text = str(exception)
			if interp._is_recoverable_runtime_error(error_text):
				interp.logger.warning(f"Recoverable interpreter error: {error_text}")
				display_markdown_message(f"Request failed: {interp._format_runtime_error_message(error_text)}")
				display_markdown_message("Try `/model <name>` to switch models or `/list` to see the available options.")
				continue
			interp.logger.error(f"An error occurred in interpreter_lib: {error_text}")
			raise
