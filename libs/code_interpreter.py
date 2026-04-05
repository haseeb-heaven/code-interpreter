"""
This is the Code Interpreter class. It provides all methods for Code LLM like Display, Execute, Format code from different llm's.
It includes features like:
- Code execution in multiple languages
- Code extraction from strings
- Saving code to a file
- Executing Code,Scripts
- Checking for compilers
"""

import os
import subprocess
import traceback
from libs.logger import Logger
from libs.markdown_code import display_markdown_message

class CodeInterpreter:

	def __init__(self):
		"""
		Initialize the CodeInterpreter instance and configure its logger.
		
		Sets self.logger to a Logger initialized with the file "logs/code-interpreter.log".
		"""
		self.logger = Logger.initialize("logs/code-interpreter.log")

	def _get_subprocess_security_kwargs(self, sandbox_context=None):
		"""
		Builds subprocess keyword arguments applying working directory, environment, and OS-specific process isolation flags.
		
		Parameters:
			sandbox_context (optional): An object that may have `cwd` and `env` attributes; those values (or `None` if absent) are used to populate the corresponding subprocess kwargs.
		
		Returns:
			dict: A mapping suitable for passing to subprocess functions containing:
			- `cwd`: the working directory from `sandbox_context.cwd` or `None`.
			- `env`: the environment mapping from `sandbox_context.env` or `None`.
			- On Windows (`os.name == "nt"`): `creationflags` (int) combining available flags such as `CREATE_NO_WINDOW` and `CREATE_NEW_PROCESS_GROUP`.
			- On non-Windows: `start_new_session` set to `True`.
		"""
		kwargs = {
			"cwd": getattr(sandbox_context, "cwd", None),
			"env": getattr(sandbox_context, "env", None),
		}
		if os.name == "nt":
			creationflags = 0
			creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
			creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
			kwargs["creationflags"] = creationflags
		else:
			kwargs["start_new_session"] = True
		return kwargs

	def _build_command_invocation(self, command: str):
		"""
		Constructs a platform-appropriate command invocation list suitable for passing to subprocess functions.
		
		Parameters:
			command (str): The shell command string to execute.
		
		Returns:
			list: A list of program and argument tokens that invoke the given command on the current OS (Windows uses `cmd.exe /d /c`, Linux/macOS prefers `/bin/bash --noprofile --norc -lc` when available, otherwise `sh -c`).
		"""
		if os.name == "nt":
			return ["cmd.exe", "/d", "/c", command]
		bash_path = "/bin/bash" if os.path.exists("/bin/bash") else None
		if bash_path:
			return [bash_path, "--noprofile", "--norc", "-lc", command]
		return ["sh", "-c", command]
	
	def _execute_script(self, script: str, shell: str, sandbox_context=None):
		"""
		Execute a script using the specified shell and return its captured output and error text.
		
		Parameters:
			script (str): The script text to execute.
			shell (str): The shell to use; expected values are `"bash"`, `"powershell"`, or `"applescript"`.
			sandbox_context (optional): An object that may provide `cwd`, `env`, and `timeout_seconds` to control the subprocess environment and timeout.
		
		Returns:
			(tuple): A pair `(stdout, stderr)` where `stdout` is the trimmed standard output string or `None` if no output, and `stderr` is the trimmed standard error string or `None` if no error. On timeout, `stderr` will be `"Execution timed out."`. If an invalid `shell` is provided, returns `(None, "Invalid shell selected: <shell>")`.
		"""
		stdout = stderr = None
		try:
			popen_kwargs = {
				"stdout": subprocess.PIPE,
				"stderr": subprocess.PIPE,
			}
			popen_kwargs.update(self._get_subprocess_security_kwargs(sandbox_context))
			if shell == "bash":
				if os.path.exists("/bin/bash"):
					process = subprocess.Popen(['/bin/bash', '--noprofile', '--norc', '-lc', script], **popen_kwargs)
				else:
					process = subprocess.Popen(['bash', '-c', script], **popen_kwargs)
			elif shell == "powershell":
				process = subprocess.Popen(['powershell', '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', script], **popen_kwargs)
			elif shell == "applescript":
				process = subprocess.Popen(['osascript', '-'], stdin=subprocess.PIPE, **popen_kwargs)
			else:
				self.logger.error(f"Invalid shell selected: {shell}")
				return None, f"Invalid shell selected: {shell}"
			timeout = getattr(sandbox_context, "timeout_seconds", 30) if sandbox_context else 30
			stdout, stderr = process.communicate(timeout=timeout)
			self.logger.info(f"Output is {stdout.decode()} and error is {stderr.decode()}")
			if process.returncode != 0:
				self.logger.info(f"Error in running {shell} script: {stderr.decode()}")
		except subprocess.TimeoutExpired:
			process.kill()
			stdout, stderr = process.communicate()
			stderr = "Execution timed out."
		except Exception as exception:
			self.logger.error(f"Exception in running {shell} script: {str(exception)}")
			stderr = str(exception)
		finally:
			return stdout.decode().strip() if stdout else None, stderr.decode().strip() if stderr else None
		
	def _check_compilers(self, language):
		try:
			language = language.lower().strip()
			
			compilers = {
				"python": ["python", "--version"],
				"javascript": ["node", "--version"],
			}

			if language not in compilers:
				self.logger.error("Invalid language selected.")
				return False

			compiler = subprocess.run(compilers[language], capture_output=True, text=True)
			if compiler.returncode != 0:
				self.logger.error(f"{language.capitalize()} compiler not found.")
				return False

			return True
		except Exception as exception:
			self.logger.error(f"Error occurred while checking compilers: {exception}")
			raise Exception(f"Error occurred while checking compilers: {exception}")
	
	def save_code(self, filename='output/code_generated.py', code=None):
		"""
		Saves the provided code to a file.
		The default filename is 'code_generated.py'.
		"""
		try:
			# Check if the directory exists, if not create it
			directory = os.path.dirname(filename)
			if not os.path.exists(directory):
				os.makedirs(directory)
			
			if not code:
				self.logger.error("Code not provided.")
				display_markdown_message("Error **Code not provided to save.**")
				return

			with open(filename, 'w') as file:
				file.write(code)
				self.logger.info(f"Code saved successfully to {filename}.")
		except Exception as exception:
			self.logger.error(f"Error occurred while saving code to file: {exception}")
			raise Exception(f"Error occurred while saving code to file: {exception}")

	def extract_code(self, code: str, start_sep='```', end_sep='```', skip_first_line=False, code_mode=False):
		"""
		Extracts a code snippet delimited by the provided start and end separators from a text block.
		
		If the input contains triple backticks ("```") but the provided separators are single backticks, the function treats the separators as triple backticks. When a matching fenced region is found, the content between the separators is returned with optional adjustments described below; if no matching separators are present, the original `code` string is returned.
		
		Parameters:
			code (str): The input text containing code or plain text. If `None`, the function returns `None`.
			start_sep (str): Opening separator that marks the start of the code block (default: "```").
			end_sep (str): Closing separator that marks the end of the code block (default: "```").
			skip_first_line (bool): When True and `code_mode` is True, skip the first line of the fenced block if the opening separator is not immediately followed by a newline.
			code_mode (bool): When True, treat the extracted content as code (affects `skip_first_line` behavior). When False, non-code cleanup is applied (see returns).
		
		Returns:
			str or None: The extracted code block (possibly adjusted), the original `code` string if no matching separators are found, or `None` if the input `code` is `None`.
		"""
		try:
			if code is None:
				self.logger.error("No content were generated by the LLM.")
				display_markdown_message("Error: **No content were generated by the LLM.**")
				return None

			# Many legacy configs still specify single backticks, but modern providers
			# usually return fenced triple-backtick blocks. Prefer triple fences when present.
			if "```" in code and (start_sep == '`' or end_sep == '`'):
				start_sep = "```"
				end_sep = "```"

			has_newline = False
			if start_sep in code and end_sep in code:
				start = code.find(start_sep) + len(start_sep)
				# Skip the newline character after the start separator
				if code[start] == '\n':
					start += 1
					has_newline = True
					
				end = code.find(end_sep, start)
				# Skip the newline character before the end separator
				if code[end - 1] == '\n':
					end -= 1
					
				if skip_first_line and code_mode and not has_newline:
					# Skip the first line after the start separator
					start = code.find('\n', start) + 1
					
				extracted_code = code[start:end]
				# Remove extra words for commands present.
				if not code_mode and 'bash' in extracted_code:
					extracted_code = extracted_code.replace('bash', '')
				
				self.logger.info("Code extracted successfully.")
				return extracted_code
			else:
				self.logger.info("No special characters found in the code. Returning the original code.")
				return code
		except Exception as exception:
			self.logger.error(f"Error occurred while extracting code: {exception}")
			raise Exception(f"Error occurred while extracting code: {exception}")
		  
	def execute_code(self, code, language, sandbox_context=None):
		"""
		Execute the provided source code in the specified language and return its captured output and errors.
		
		Executes `code` using a subprocess for the given `language` and returns the subprocess stdout and stderr as decoded UTF-8 strings. Supports "python" (runs `python -c`) and "javascript" (runs `node -e`). Applies optional sandboxing parameters from `sandbox_context` (cwd, env, and timeout_seconds) to the subprocess invocation.
		
		Parameters:
			code (str): Source code to execute.
			language (str): Programming language name (e.g., "python", "javascript").
			sandbox_context (optional): An object that may provide `cwd`, `env`, and `timeout_seconds` to control subprocess execution and timeout.
		
		Returns:
			tuple: `(stdout, stderr)` where each is a decoded UTF-8 string containing the subprocess standard output and standard error.
			str: If the provided `code` is empty or only whitespace, returns the message "Code is empty. Cannot execute an empty code."
			tuple: `(None, "Execution timed out.")` if the subprocess exceeds the configured timeout.
		
		Raises:
			Exception: If required compilers/interpreters are not found, if the language is unsupported, or on other execution errors.
		"""
		try:
			language = language.lower()
			self.logger.info(f"Running code: {code[:100]} in language: {language}")

			# Check for code and language validity
			if not code or len(code.strip()) == 0:
				return "Code is empty. Cannot execute an empty code."
			
			# Check for compilers on the system
			compilers_status = self._check_compilers(language)
			if not compilers_status:
				raise Exception("Compilers not found. Please install compilers on your system.")
			
			if language == "python":
				process = subprocess.Popen(
					["python", "-c", code],
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
					**self._get_subprocess_security_kwargs(sandbox_context),
				)
				timeout = getattr(sandbox_context, "timeout_seconds", 30) if sandbox_context else 30
				stdout, stderr = process.communicate(timeout=timeout)
				stdout_output = stdout.decode("utf-8")
				stderr_output = stderr.decode("utf-8")
				self.logger.info(f"Python Output execution: {stdout_output}, Errors: {stderr_output}")
				return stdout_output, stderr_output
			
			elif language == "javascript":
				process = subprocess.Popen(
					["node", "-e", code],
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
					**self._get_subprocess_security_kwargs(sandbox_context),
				)
				timeout = getattr(sandbox_context, "timeout_seconds", 30) if sandbox_context else 30
				stdout, stderr = process.communicate(timeout=timeout)
				stdout_output = stdout.decode("utf-8")
				stderr_output = stderr.decode("utf-8")
				self.logger.info(f"JavaScript Output execution: {stdout_output}, Errors: {stderr_output}")
				return stdout_output, stderr_output
			
			else:
				self.logger.info("Unsupported language.")
				raise Exception("Unsupported language.")
		except subprocess.TimeoutExpired:
			process.kill()
			process.communicate()
			return None, "Execution timed out."
				
		except Exception as exception:
			self.logger.error(f"Exception in running code: {str(exception)}")
			raise exception
		
	def execute_script(self, script:str, os_type:str='macos', sandbox_context=None):
		"""
		Execute a platform-specific script and return its captured output and error.
		
		Parameters:
			script (str): The script content to run.
			os_type (str): Target operating system; recognized values include 'macos', 'linux', and 'windows' (case-insensitive).
			sandbox_context (optional): Sandbox configuration object (e.g., providing `cwd`, `env`, and `timeout_seconds`) applied to the subprocess invocation.
		
		Returns:
			tuple: (stdout, stderr) where `stdout` is the script's standard output string or None, and `stderr` is the script's standard error string or None.
		
		Raises:
			ValueError: If `script` or `os_type` is missing, or if `os_type` is not one of 'macos', 'linux', or 'windows'.
		"""
		output = error = None
		try:
			if not script:
				raise ValueError("Script must be provided.")
			if not os_type:
				raise ValueError("OS type must be provided.")

			self.logger.info(f"Attempting to execute script: {script[:50]}")
			if any(os in os_type.lower() for os in ['darwin', 'macos']):
				output, error = self._execute_script(script, shell='applescript', sandbox_context=sandbox_context)
			elif 'linux' in os_type.lower():
				output, error = self._execute_script(script, shell='bash', sandbox_context=sandbox_context)
			elif 'windows' in os_type.lower():
				output, error = self._execute_script(script, shell='powershell', sandbox_context=sandbox_context)
			else:
				raise ValueError(f"Invalid OS type '{os_type}'. Please provide 'macos', 'linux', or 'windows'.")

			if output:
				self.logger.info(f"Script executed successfully with output: {output[:50]}...")
			if error:
				self.logger.error(f"Script executed with error: {error}...")
		except Exception as exception:
			self.logger.error(f"Error in executing script: {traceback.format_exc()}")
			error = str(exception)
		finally:
			return output, error
		
	def execute_command(self, command:str, sandbox_context=None):
		"""
		Execute a shell command in a subprocess and return its captured stdout and stderr.
		
		Parameters:
			command (str): The command string to execute; must be provided.
			sandbox_context (optional): Optional object that may supply execution parameters:
				- cwd: working directory for the subprocess
				- env: environment variables mapping for the subprocess
				- timeout_seconds: execution timeout in seconds (defaults to 30)
				Additionally used to determine OS-specific subprocess kwargs (e.g., creationflags or start_new_session).
		
		Returns:
			tuple: (stdout, stderr)
			- stdout (str or None): UTF-8 decoded standard output from the command, or None if execution timed out.
			- stderr (str): UTF-8 decoded standard error from the command, or the string "Execution timed out." if the process exceeded the timeout.
		
		Raises:
			ValueError: If `command` is empty or not provided.
			Exception: Re-raises any unexpected exceptions encountered during execution.
		"""
		try:
			if not command:
				raise ValueError("Command must be provided.")
  
			self.logger.info(f"Attempting to execute command: {command}")
			process = subprocess.run(
				self._build_command_invocation(command),
				shell=False,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				timeout=getattr(sandbox_context, "timeout_seconds", 30) if sandbox_context else 30,
				**self._get_subprocess_security_kwargs(sandbox_context),
			)

			stdout_output = process.stdout.decode("utf-8")
			stderr_output = process.stderr.decode("utf-8")
  
			if stdout_output:
				self.logger.info(f"Command executed successfully with output: {stdout_output}")
			if stderr_output:
				self.logger.info(f"Command executed with error: {stderr_output}")
  
			return stdout_output, stderr_output
		except subprocess.TimeoutExpired:
			return None, "Execution timed out."
		except Exception as exception:
			self.logger.error(f"Error in executing command: {str(exception)}")
			raise exception

