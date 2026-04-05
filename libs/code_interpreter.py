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
		self.logger = Logger.initialize("logs/code-interpreter.log")

	def _get_subprocess_security_kwargs(self, sandbox_context=None):
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
		if os.name == "nt":
			return ["cmd.exe", "/d", "/c", command]
		bash_path = "/bin/bash" if os.path.exists("/bin/bash") else None
		if bash_path:
			return [bash_path, "--noprofile", "--norc", "-lc", command]
		return ["sh", "-c", command]
	
	def _execute_script(self, script: str, shell: str, sandbox_context=None):
		stdout_val = stderr_val = None
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
				stderr_val = f"Invalid shell selected: {shell}".encode()
			if stderr_val is not None:
				return (stdout_val, stderr_val.decode().strip() if isinstance(stderr_val, bytes) else stderr_val)
			timeout = getattr(sandbox_context, "timeout_seconds", 30) if sandbox_context else 30
			stdout_val, stderr_val = process.communicate(timeout=timeout)
			if self.logger:
				self.logger.info(f"Output is {stdout_val.decode()} and error is {stderr_val.decode()}")
			if process.returncode != 0:
				if self.logger:
					self.logger.info(f"Error in running {shell} script: {stderr_val.decode()}")
		except subprocess.TimeoutExpired as timeout_exc:
			process.kill()
			process.communicate()
			stderr_val = b"Execution timed out."
		except Exception as exception:
			if self.logger:
				self.logger.error(f"Exception in running {shell} script: {str(exception)}")
			stderr_val = str(exception).encode()
		return (stdout_val.decode().strip() if stdout_val else None, stderr_val.decode().strip() if isinstance(stderr_val, bytes) else stderr_val)
		
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
		Extracts the code from the provided string.
		If the string contains the start and end separators, it extracts the code between them.
		Otherwise, it returns the original string.
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
			raise TimeoutError("Execution timed out.")

		except Exception as exception:
			self.logger.error(f"Exception in running code: {str(exception)}")
			raise exception
		
	def execute_script(self, script:str, os_type:str='macos', sandbox_context=None):
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