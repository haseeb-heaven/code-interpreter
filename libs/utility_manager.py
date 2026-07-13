import os
import platform
import re
import subprocess
from dotenv import load_dotenv
from libs.code_interpreter import CodeInterpreter
from libs.logger import Logger
import csv
import glob
from datetime import datetime

from libs.core.model_registry import ModelRegistry
from libs.markdown_code import display_code, display_markdown_message


class UtilityManager:
	logger = None

	def __init__(self):
		try:
			if not os.path.exists('logs'):
				os.makedirs('logs')
			if not os.path.isfile('logs/interpreter.log'):
				open('logs/interpreter.log', 'w').close()
		except Exception as exception:
			self.logger.error(f"Error in UtilityManager initialization: {str(exception)}")
			raise
		self.logger = Logger.initialize("logs/interpreter.log")

	def _open_resource_file(self, filename):
		try:
			if os.path.isfile(filename):
				if platform.system() == "Windows":
					os.startfile(filename)
				elif platform.system() == "Darwin":
					subprocess.call(['open', filename])
				elif platform.system() == "Linux":
					subprocess.call(['xdg-open', filename])
				self.logger.info(f"{filename} exists and opened successfully")
		except Exception as exception:
			display_markdown_message(f"Error in opening files: {str(exception)}")

	def _clean_responses(self):
		files_to_remove = ['graph.png', 'chart.png', 'table.md']
		for file in files_to_remove:
			try:
				if os.path.isfile(file):
					os.remove(file)
					self.logger.info(f"{file} removed successfully")
			except Exception as e:
				print(f"Error in removing {file}: {str(e)}")
	
	def _extract_content(self, output):
		try:
			if output is None:
				return ""
			if isinstance(output, str):
				return output
			
			if hasattr(output, 'choices') and len(output.choices) > 0:
				# Some providers/models (e.g. reasoning models that only emit
				# tool calls or reasoning tokens) return content=None on an
				# otherwise-successful response; coalesce so callers always
				# get a string instead of crashing on None downstream.
				return output.choices[0].message.content or ""
			elif isinstance(output, dict):
				if 'choices' in output and len(output['choices']) > 0:
					return output['choices'][0]['message']['content'] or ""
				elif 'response' in output:
					return output['response']

			return output['choices'][0]['message']['content'] or ""
		except (KeyError, TypeError, AttributeError) as e:
			self.logger.error(f"Error extracting content: {str(e)}. Output: {output}")
			return ""
	
	def get_os_platform(self):
		try:
			os_info = platform.uname()
			os_name = os_info.system
			os_version = os_info.release

			if os_name == 'Linux':
				# Attempt to get distribution info
				try:
					import distro
					distro_info = distro.info()
					os_name = f"{os_name} ({distro_info['id']} {distro_info['version_parts']['major']})" # e.g., "Linux (ubuntu 22)"
				except ImportError:
					self.logger.warning("distro package not found.  Linux distribution details will be less specific.")
					# Fallback if distro is not installed
					os_name = f"{os_name} ({os_version})"
			elif os_name == 'Windows':
				os_name = f"{os_name} {platform.version()}"
			elif os_name == 'Darwin':  # macOS
				os_name = f"{os_name} {platform.mac_ver()[0]}"

			self.logger.info(f"Operating System: {os_name}")
			return os_name, os_info.version
		except Exception as exception:
			self.logger.error(f"Error in getting OS platform: {str(exception)}")
			raise

	def initialize_readline_history(self):
		try:
			try:
				import readline
			except ImportError:
				try:
					# pyreadline3 (modern) then legacy pyreadline for older envs.
					import pyreadline3 as readline  # type: ignore
				except ImportError:
					try:
						import pyreadline as readline  # type: ignore
					except ImportError:
						self.logger.info(
							"Readline support is unavailable. Continuing without input history."
						)
						return False
				
			histfile = os.path.join(os.path.expanduser("~"), ".python_history")
			
			# Check if histfile exists before trying to read it
			if os.path.exists(histfile):
				readline.read_history_file(histfile)
			
			# Save history to file on exit
			import atexit
			atexit.register(readline.write_history_file, histfile)
			return True
			
		except FileNotFoundError:
			self.logger.info("History file not found. Continuing without persisted input history.")
			return False
		
		except AttributeError:
			# Handle error on Windows where pyreadline doesn't have read_history_file
			self.logger.info("Readline history is not supported on this platform. Continuing without input history.")
			return False
		except Exception as exception:
			self.logger.info(f"Skipping readline history initialization: {str(exception)}")
			return False

	@staticmethod
	def _normalize_model_key(name):
		"""Accept a bare model key or a legacy ``configs/<name>.json`` path."""
		key = str(name or "").strip()
		for prefix in ("configs/", "configs\\"):
			if key.startswith(prefix):
				key = key[len(prefix):]
		if key.lower().endswith(".json"):
			key = key[: -len(".json")]
		return key

	def read_config_file(self, filename=None):
		"""Look up a model entry in the ``configs/models.toml`` registry.

		``filename`` may be a bare model key (``"gpt-4o"``) or a legacy
		``configs/<name>.json`` style path for backwards compatibility.
		"""
		if not filename:
			raise ValueError("Config filename must be provided.")
		name = self._normalize_model_key(filename)
		try:
			registry = ModelRegistry.load()
			config = registry.get_model(name)
			if config is None:
				raise KeyError(
					f"Model '{name}' not found in model registry ({registry.path})."
				)
			return config
		except Exception as exception:
			self.logger.error(f"Error in reading config file: {str(exception)}")
			raise

	def list_available_models(self, configs_path=None):
		try:
			registry = ModelRegistry.load(configs_path)
			return registry.list_model_names()
		except Exception as exception:
			self.logger.error(f"Error in listing available models: {str(exception)}")
			raise

	@staticmethod
	def get_default_model_name():
		env_path = os.path.join(os.getcwd(), ".env")
		load_dotenv(dotenv_path=env_path, override=False)
		registry = ModelRegistry.load()
		return registry.default_model_name(environ=os.environ)

	def extract_file_name(self, prompt):
		try:
			# This pattern looks for typical file paths, names, and URLs, then stops at the end of the extension
			pattern = r"((?:[a-zA-Z]:\\(?:[\w\-\.]+\\)*|/(?:[\w\-\.]+/)*|\b[\w\-\.]+\b|https?://[\w\-\.]+/[\w\-\.]+/)*[\w\-\.]+\.\w+)"
			match = re.search(pattern, prompt)

			# Return the matched file name or path, if any match found
			if match:
				file_name = match.group()
				file_extension = os.path.splitext(file_name)[1].lower()
				self.logger.info(f"File extension: '{file_extension}'")
				# Check if the file extension is one of the non-binary types
				if file_extension in ['.json', '.csv', '.xml', '.xls', '.txt', '.md', '.html', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.zip', '.tar', '.gz', '.7z', '.rar']:
					self.logger.info(f"Extracted File name: '{file_name}'")
					return file_name
				else:
					return None
			else:
				return None
		except Exception as exception:
			self.logger.error(f"Error in extracting file name: {str(exception)}")
			raise

	@staticmethod
	def _is_explicit_absolute_path(path: str) -> bool:
		"""True for host absolute paths, including Windows drive/UNC forms on any OS.

		Prompt text often contains ``D:\\demo\\file.jpg``. On POSIX hosts,
		``os.path.isabs`` does not treat drive-letter paths as absolute, so we
		detect those forms explicitly for consistent input-file resolution.

		Python 3.13+ on Windows also reports ``isabs('/tmp/x') == False`` for
		drive-less root paths; treat a leading ``/`` or ``\\`` as explicit
		absolute user intent for prompt input resolution.
		"""
		if not path:
			return False
		if os.path.isabs(path):
			return True
		# Windows drive-letter absolute: D:\foo or D:/foo
		if re.match(r"^[A-Za-z]:[\\/]", path):
			return True
		# Windows UNC: \\server\share\...
		if path.startswith("\\\\") and len(path) > 2:
			return True
		# POSIX absolute, or Windows drive-less root (/tmp, \Windows\...)
		if path.startswith("/") or (path.startswith("\\") and not path.startswith("\\\\")):
			return True
		return False

	def get_full_file_path(self, file_name, *, allow_absolute=True):
		"""Resolve a user-named input file path with traversal protection.

		Relative paths must resolve under the current working directory.
		Explicit absolute paths (Windows drive letter, UNC, or POSIX ``/``)
		are allowed by default for *input* file reads named in the prompt
		(image convert, CSV attach, etc.). Write/exec sandboxing remains
		enforced elsewhere (SAFE MODE / SafetyManager).

		Pass ``allow_absolute=False`` for relative-only / sandbox-root policy;
		that raises a clear sandbox error instead of "Path traversal".
		"""
		if not file_name:
			return None

		expanded = os.path.expanduser(str(file_name).strip())
		if self._is_explicit_absolute_path(expanded):
			if not allow_absolute:
				raise ValueError(
					"Security Error: Absolute paths outside sandbox not allowed: "
					f"{file_name}. Place the file under the working directory, "
					"or use --no-sandbox for unrestricted access."
				)
			# User-explicit absolute input path: normalize without forcing under cwd.
			# Drive-letter paths on non-Windows hosts must not be joined to cwd.
			if re.match(r"^[A-Za-z]:[\\/]", expanded) and os.name != "nt":
				return os.path.normpath(expanded)
			return os.path.abspath(expanded)

		cwd = os.path.abspath(os.getcwd())
		full_path = os.path.abspath(os.path.join(cwd, expanded))

		try:
			common_path = os.path.commonpath([cwd, full_path])
		except ValueError as e:
			# Raised on Windows when paths are on different drives
			raise ValueError(f"Security Error: Path traversal attempt detected: {file_name}") from e

		if os.path.normcase(common_path) != os.path.normcase(cwd):
			raise ValueError(f"Security Error: Path traversal attempt detected: {file_name}")

		return full_path
	
	def read_csv_headers(self, file_path):
		try:
			with open(file_path, newline='') as csvfile:
				reader = csv.reader(csvfile)
				headers = next(reader)
				return headers
		except IOError as exception:
			self.logger.error(f"IOError: {exception}")
			return []
		except StopIteration:
			self.logger.error("CSV file is empty.")
			return []

	def get_output_history(self, mode='code', os_name=None, language=None):
		try:
			self.logger.info("Starting to read last code history.")
			output_folder = "output"
			
			extensions = {
				"code": {
					"python": ['.py'],
					"javascript": ['.js'],
				},
				"command": {
					"darwin": ['.sh'],
					"linux": ['.sh'],
					"windows": ['.bat']
				},
				"script": {
					"darwin": ['.applescript'],
					"linux": ['.sh'],
					"windows": ['.bat']
				}
			}

			name = language if mode.lower() == 'code' else re.split(r'\s+', os_name.lower())[0]

			for extension in extensions[mode][name]:
				# Get a list of all files in the output folder with the correct extension
				files = glob.glob(os.path.join(output_folder, f"*{extension}"))
				self.logger.info(f"Found {len(files)} files.")

				# Sort the files by date
				files.sort(key=lambda x: datetime.strptime(x.split('_', 1)[1].rsplit('.', 1)[0], '%Y_%m_%d-%H_%M_%S'), reverse=True)
				self.logger.info("Files sorted by date.")

				# Return the latest file
				latest_file = files[0] if files else None
				self.logger.info(f"Latest file: {latest_file}")

				# Read the file and return the code
				if latest_file:
					with open(latest_file, "r", encoding="utf-8", errors="replace") as code_file:
						code = code_file.read()
						return latest_file, code
			
			return None, None

		except Exception as exception:
			self.logger.error(f"Error in reading last code history: {str(exception)}")
			raise

	def display_help(self):
		msg = (
			"Interpreter\n\n"
			"Startup flags:\n\n"
			"--cli - Launch the classic prompt-based CLI.\n"
			"--tui - Launch the selector-based terminal UI.\n\n"
			"Commands available:\n\n"
			"/exit - Exit the interpreter.\n"
			"/execute - Execute the last code generated.\n"
			"/install - Install a package from npm or pip.\n"
			"/save - Save the last code generated.\n"
			"/edit - Edit the last code generated.\n"
			"/fix - Fix the last code generated.\n"
			"/mode - Change the mode of interpreter.\n"
			"/model - Change the model for interpreter.\n"
			"/language - Change the language of the interpreter.\n"
			"/history - Use history as memory.\n"
			"/memory show|clear|stats - Inspect or clear context memory.\n"
			"/session save|clear|info - Manage persistent --session state.\n"
			"/sessions - List all saved sessions.\n"
			"/clear - Clear the screen.\n"
			"/help - Display this help message.\n"
			"/list - List the available models.\n"
			"/free - List curated free/cheap LLM presets.\n"
			"/image <path-or-url> - Attach an image for a multimodal question.\n"
			"/file <path> - Attach a local data file to the next tasks.\n"
			"/files - List currently attached local files.\n"
			"/clear-files - Detach all local files.\n"
			"/eda <path> - Offline exploratory data analysis on a local file.\n"
			"/charts [open N|dir] - List or open saved charts.\n"
			"/export csv|excel|json|markdown|html|report - Export active dataset.\n"
			"/clean nulls|dupes|types|dates|whitespace|all - Clean active dataset.\n"
			"/sql <query|question> - Run SQL (or NL→SQL) on the active dataset.\n"
			"/templates data|files|viz - Show prompt templates.\n"
			"/chart-style plotly|matplotlib - Prefer interactive or static charts.\n"
			"/notebook [path|open] - Export session as Jupyter .ipynb.\n"
			"/ml classify|regress|cluster - Quick sklearn shortcuts on active data.\n"
			"/output full - Write last full (untruncated) stdout to a temp file.\n"
			"/search <query> - Search the web (DuckDuckGo / Tavily / Serper).\n"
			"/version - Display the version of the interpreter.\n"
			"/debug - Switch between debug and silent mode.\n"
			"/prompt - Switch input prompt mode between file and prompt.\n"
			"/upgrade - Upgrade the interpreter.\n"
			"/sandbox - Toggle sandbox mode at runtime.\n"
			"/audit [full|clear] - Show or manage the execution audit log.\n"
			"/key-status - Show API key pool / circuit breaker status.\n"
			"/reload-keys - Reload API keys from .env without restart.\n"
			"/metrics - Show LLM call metrics summary.\n"
		)
		display_markdown_message(msg)
	def display_version(self, version):
		display_markdown_message(f"Interpreter - v{version}")

	def clear_screen(self, redraw_banner: bool = True):
		"""Clear the terminal.

		Every clear-screen call site in this codebase (the ``/clear`` REPL
		command, prompt-mode switches, and the arrow-key TUI wizard's
		selector redraws) routes through this single choke point, so
		redrawing the persistent INTERPRETER banner immediately after
		clearing here makes the banner visually "stay pinned" to the top of
		the screen everywhere a clear happens. Pass ``redraw_banner=False``
		for the rare bare, banner-free clear.
		"""
		os.system('cls' if os.name == 'nt' else 'clear')
		if redraw_banner:
			try:
				from libs.agent.gemini_ui import render_persistent_banner

				render_persistent_banner()
			except Exception as exc:
				self.logger.debug(f"Persistent banner redraw skipped: {exc}")
	
	def create_file(self, file_path):
		try:
			with open(file_path, "w", encoding="utf-8") as file:
				file.write("")
		except Exception as exception:
			self.logger.error(f"Error in creating file: {str(exception)}")
			raise
		
	def read_file(self, file_path):
		try:
			with open(file_path, "r", encoding="utf-8", errors="replace") as file:
				return file.read()
		except Exception as exception:
			self.logger.error(f"Error in reading file: {str(exception)}")
			raise
	
	def write_file(self, file_path, content):
		try:
			with open(file_path, "w", encoding="utf-8", errors="strict") as file:
				file.write(content)
		except Exception as exception:
			self.logger.error(f"Error in writing file: {str(exception)}")
			raise
	
	# method to download file from Web and save it
	
	@staticmethod
	def _download_file(url, file_name):
		try:
			logger = Logger.initialize("logs/interpreter.log")
			import requests
			logger.info(f"Downloading file: {url}")
			response = requests.get(url, allow_redirects=True, timeout=10)
			response.raise_for_status()
			
			with open(file_name, 'wb') as file:
				file.write(response.content)
				logger.info("Reuquirements.txt file downloaded.")
			return True
		except Exception as exception:
			logger.error(f"Error in downloading file: {str(exception)}")
			return False

	@staticmethod
	def upgrade_interpreter():
		code_interpreter = CodeInterpreter()
		logger = Logger.initialize("logs/interpreter.log")
		# Download the requirements file
		file_url = 'https://raw.githubusercontent.com/haseeb-heaven/code-interpreter/main/requirements.txt'
		requirements_file_downloaded = UtilityManager._download_file(file_url, 'requirements.txt')
		
		# Commands to execute.
		command_pip_upgrade = 'pip install open-code-interpreter --upgrade'
		command_pip_requirements = 'pip install -r requirements.txt --upgrade'
		
		# Execute the commands.
		command_output, _ = code_interpreter.execute_command(command_pip_upgrade)
		display_markdown_message("Command Upgrade executed successfully.")
		if requirements_file_downloaded:
			command_output, _ = code_interpreter.execute_command(command_pip_requirements)
			display_markdown_message("Command Requirements executed successfully.")
		else:
			logger.warn("Requirements file not downloaded.")
			display_markdown_message("Warning: Requirements file not downloaded.")
		
		if command_output:
			logger.info("Command executed successfully.")
			display_code(command_output)
			logger.info(f"Output: {command_output[:100]}")
