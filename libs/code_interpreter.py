"""
This is the Code Interpreter class. It provides all methods for Code LLM like Display, Execute, Format code from different llm's.
It includes features like:
- Code execution in multiple languages
- Code extraction from strings
- Saving code to a file
- Executing Code,Scripts
- Checking for compilers
"""

import ast
import os
import re
import subprocess
import traceback
import tempfile
import shlex
import shutil
import signal
try:
	import resource
except Exception:
	resource = None
from libs.logger import Logger
from libs.markdown_code import display_markdown_message
from libs.safety_manager import ExecutionSafetyManager

# Maximum stdout/stderr to capture (characters) to avoid unbounded memory use
MAX_OUTPUT = 10_000_000  # 10 MB
MAX_TIMEOUT = 120  # 2 minutes (safe mode only)

def _limit_resources():
	"""Apply basic resource limits in the child process (Unix only). Safe mode only."""
	if resource is None:
		return
	try:
		# CPU seconds (soft, hard)
		resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
		# Address space (virtual memory) ~256MB
		resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
		# Limit number of processes
		try:
			resource.setrlimit(resource.RLIMIT_NPROC, (50, 50))
		except Exception:
			pass
	except Exception:
		pass

# Common GitHub-flavored markdown fence language tags; first line after ``` is stripped when it matches.
_FENCE_LANGUAGE_TAGS = frozenset({
	"asm", "bash", "bat", "c", "clojure", "cljs", "cmd", "cpp", "cs", "csharp", "css", "cxx", "c++",
	"dart", "diff", "dockerfile", "elixir", "erl", "erlang", "ex", "exs", "fish", "go", "golang",
	"graphql", "gql", "graphqls", "haskell", "hs", "html", "htm", "java", "javascript", "jl", "js",
	"json", "julia", "jsx", "kt", "kotlin", "less", "lua", "makefile", "markdown", "matlab", "md", "m",
	"ml", "nginx", "objc", "objective-c", "ocaml", "octave", "patch", "perl", "php", "plaintext",
	"powershell", "protobuf", "proto", "ps1", "py", "py3", "python", "python3", "r", "rb", "ruby",
	"rust", "rs", "sass", "scala", "scss", "sh", "shell", "sol", "solidity", "sql", "swift", "text",
	"toml", "ts", "tsx", "txt", "typescript", "vb", "vbnet", "vim", "xml", "yaml", "yml", "zig",
	"zsh", "wasm", "llvm", "hcl", "terraform", "tf",
})


def _is_python_code(script: str) -> bool:
	"""Return True if *script* is valid Python, by attempting ast.parse().

	This replaces the old regex heuristic (_PYTHON_CODE_PATTERNS) which
	false-positived on bash constructs like 'for x in *.txt; do ... done'
	and 'while true; do ... done', routing valid shell scripts to the
	Python executor where they die with SyntaxError.
	"""
	try:
		ast.parse(script)
		return True
	except SyntaxError:
		return False


def _strip_leading_fence_language_line(extracted: str) -> str:
	if not extracted:
		return extracted
	if "\n" not in extracted:
		line = extracted.strip()
		if line.lower() in _FENCE_LANGUAGE_TAGS:
			return ""
		return extracted
	first, rest = extracted.split("\n", 1)
	if first.strip().lower() in _FENCE_LANGUAGE_TAGS:
		return rest
	return extracted


def _kill_process_group(process):
	"""Kill a subprocess and its entire process group (POSIX) or just the process (Windows)."""
	try:
		if os.name != "nt":
			os.killpg(os.getpgid(process.pid), signal.SIGKILL)
		else:
			process.kill()
	except Exception:
		# Fallback: kill direct child only
		try:
			process.kill()
		except Exception:
			pass


class CodeInterpreter:

	def __init__(self, safety_manager=None):
		self.logger = Logger.initialize("logs/code-interpreter.log")

		if safety_manager is None:
			self.safety_manager = ExecutionSafetyManager()
		else:
			self.safety_manager = safety_manager

		self.UNSAFE_EXECUTION = self.safety_manager.unsafe_mode if self.safety_manager else False

	def _is_unsafe(self) -> bool:
		"""Live check of unsafe mode — honours runtime toggles via /unsafe command."""
		return bool(getattr(self.safety_manager, 'unsafe_mode', False))

	def _get_subprocess_security_kwargs(self, sandbox_context=None):
		if sandbox_context is None:
			kwargs = {"cwd": None, "env": None}
			if os.name == "nt":
				creationflags = 0
				creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
				creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
				kwargs["creationflags"] = creationflags
			else:
				kwargs["start_new_session"] = True
			return kwargs

		cwd = getattr(sandbox_context, "cwd", None)
		allowed_keys = {"PATH", "HOME", "LANG"}
		if hasattr(sandbox_context, "env"):
			provided_env = getattr(sandbox_context, "env")
			if os.name == "nt":
				default_env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("USERPROFILE", ""), "LANG": os.environ.get("LANG", "C")}
			else:
				default_env = {"PATH": "/usr/bin:/bin", "HOME": tempfile.gettempdir(), "LANG": "C"}
			safe_env = default_env.copy()
			if isinstance(provided_env, dict):
				for k in allowed_keys:
					if k in provided_env and provided_env[k] is not None:
						safe_env[k] = provided_env[k]
				env = safe_env
			else:
				env = provided_env
		else:
			env = None

		kwargs = {"cwd": cwd, "env": env}
		if os.name == "nt":
			creationflags = 0
			creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)
			creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
			kwargs["creationflags"] = creationflags
		else:
			kwargs["start_new_session"] = True
		return kwargs

	def _normalize_command(self, command: str) -> str:
		command = command.strip()

		command_lower = command.lower()

		# WINDOWS / GENERIC FILE LISTING
		if re.search(r'\b(dir|ls|get-childitem)\b', command_lower):
			if ".txt" in command_lower:

				# extract path
				match = re.search(r"(?:from|path)?\s*['\"]?([a-zA-Z]:[\\/][^'\"]+)['\"]?", command)
				path = match.group(1) if match else "."

				return (
					f'python -c "import pathlib; '
					f'print(\'\\n\'.join(str(p) for p in pathlib.Path(r\'{path}\').rglob(\'*.txt\')))"'
				)

		# CURRENT DIRECTORY
		if "pwd" in command_lower or "current directory" in command_lower:
			return 'python -c "import os; print(os.getcwd())"'

		# LIST FILES GENERIC
		if command_lower.strip() in ["ls", "dir"]:
			return 'python -c "import os; print(\'\\n\'.join(os.listdir()))"'

		# FALLBACK (no change)
		return command

	def _build_command_invocation(self, command: str):
		command = command.strip()
		command_lower = command.lower()

		try:
			if command_lower.startswith("python -c"):
				parts = command.split(" ", 2)
				if len(parts) < 3:
					raise ValueError("Invalid python -c format")
				first, second, rest = parts
				if (rest.startswith('"') and rest.endswith('"')) or (rest.startswith("'") and rest.endswith("'")):
					rest = rest[1:-1]
				return [first, second, rest]

			if command_lower.startswith("node -e"):
				parts = command.split(" ", 2)
				if len(parts) < 3:
					raise ValueError("Invalid node -e format")
				first, second, rest = parts
				if (rest.startswith('"') and rest.endswith('"')) or (rest.startswith("'") and rest.endswith("'")):
					rest = rest[1:-1]
				return [first, second, rest]

		except Exception as e:
			raise ValueError(f"Invalid inline command format: {command}") from e

		if os.name != "nt":
			try:
				parts = shlex.split(command)
				if not parts:
					raise ValueError("Empty command")
				return parts
			except Exception as e:
				raise ValueError(f"Invalid command format: {command}") from e
		else:
			try:
				parts = shlex.split(command, posix=False)
				if not parts:
					raise ValueError("Empty command")
				if any(op in command for op in ["&", "|", "&&", ">", "<"]):
					raise ValueError("Shell operators not allowed")
				return parts
			except Exception as e:
				raise ValueError(f"Invalid command format: {command}") from e

	def _execute_script(self, script: str, shell: str, sandbox_context=None):
		"""Execute a script.
		In SAFE mode: isolated temp dir, resource limits, and timeout apply.
		In UNSAFE mode: no sandbox, no timeout, full system access.
		"""
		stdout_decoded = stderr_decoded = None
		process = None
		safe_dir = None
		temp_script_path = None

		unsafe = self._is_unsafe()

		try:
			popen_kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE}

			if unsafe:
				# UNSAFE MODE: run in the real CWD, inherit the full environment,
				# no timeout, no resource limits.
				safe_dir = os.getcwd()
				popen_kwargs["cwd"] = safe_dir
				popen_kwargs["env"] = None  # inherit full env
				if os.name == "nt":
					creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
					creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
					popen_kwargs["creationflags"] = creationflags
				else:
					popen_kwargs["start_new_session"] = True
				timeout = None  # no timeout in unsafe mode
				posix_extra = {}  # no resource limits in unsafe mode
			else:
				# SAFE MODE: sandboxed dir, filtered env, timeout, resource limits.
				base_kwargs = self._get_subprocess_security_kwargs(sandbox_context)
				popen_kwargs.update(base_kwargs)
				safe_dir = sandbox_context.cwd if sandbox_context else tempfile.mkdtemp(prefix="ci_sandbox_")
				popen_kwargs["cwd"] = safe_dir
				timeout = getattr(sandbox_context, "timeout_seconds", MAX_TIMEOUT) if sandbox_context else MAX_TIMEOUT
				posix_extra = {"preexec_fn": _limit_resources} if os.name != "nt" else {}

				# SAFETY CHECK (safe mode only)
				decision = self.safety_manager.assess_execution(script, "script")
				if not decision.allowed:
					return None, f"Safety blocked: {'; '.join(decision.reasons)}"

			if shell == "python":
				fd, temp_script_path = tempfile.mkstemp(prefix="ci_py_", suffix=".py", dir=safe_dir)
				with os.fdopen(fd, "wb") as fh:
					fh.write(script.encode())
					fh.flush()

				exec_bin = shutil.which("python3") or shutil.which("python") or "python"
				args = [exec_bin, temp_script_path]

				if os.name != "nt":
					process = subprocess.Popen(args, **popen_kwargs, **posix_extra)
				else:
					process = subprocess.Popen(args, **popen_kwargs)

				try:
					stdout_val, stderr_val = process.communicate(timeout=timeout)
				except subprocess.TimeoutExpired:
					_kill_process_group(process)
					process.communicate()
					return None, "Execution timed out."

				stdout_decoded = stdout_val.decode(errors="ignore") if stdout_val else ""
				stderr_decoded = stderr_val.decode(errors="ignore") if stderr_val else ""

			elif shell == "bash":
				fd, temp_script_path = tempfile.mkstemp(prefix="ci_script_", suffix=".sh", dir=safe_dir)
				with os.fdopen(fd, "wb") as fh:
					fh.write(script.encode())
					fh.flush()
				os.chmod(temp_script_path, 0o700)

				args = ["/bin/bash", temp_script_path]

				if os.name != "nt":
					process = subprocess.Popen(args, **popen_kwargs, **posix_extra)
				else:
					process = subprocess.Popen(args, **popen_kwargs)

				try:
					stdout_val, stderr_val = process.communicate(timeout=timeout)
				except subprocess.TimeoutExpired:
					_kill_process_group(process)
					process.communicate()
					return None, "Execution timed out."

				stdout_decoded = stdout_val.decode(errors="ignore") if stdout_val else ""
				stderr_decoded = stderr_val.decode(errors="ignore") if stderr_val else ""

			elif shell == "applescript":
				args = ["osascript", "-"]
				if os.name != "nt":
					process = subprocess.Popen(args, stdin=subprocess.PIPE, **popen_kwargs, **posix_extra)
				else:
					process = subprocess.Popen(args, stdin=subprocess.PIPE, **popen_kwargs)
				try:
					stdout_val, stderr_val = process.communicate(input=script.encode(), timeout=timeout)
				except subprocess.TimeoutExpired:
					_kill_process_group(process)
					process.communicate()
					return None, "Execution timed out."

				stdout_decoded = stdout_val.decode(errors="ignore") if stdout_val else ""
				stderr_decoded = stderr_val.decode(errors="ignore") if stderr_val else ""

			else:
				stderr_decoded = f"Invalid shell selected: {shell}"
				return (None, stderr_decoded)

			if len(stdout_decoded) > MAX_OUTPUT:
				stdout_decoded = stdout_decoded[:MAX_OUTPUT]

			if len(stderr_decoded) > MAX_OUTPUT:
				stderr_decoded = stderr_decoded[:MAX_OUTPUT]

			return stdout_decoded, stderr_decoded

		except subprocess.TimeoutExpired:
			if process:
				_kill_process_group(process)
				try:
					process.communicate()
				except Exception:
					pass
			return None, "Execution timed out."

		except Exception as e:
			return None, str(e)

		finally:
			try:
				if temp_script_path and os.path.exists(temp_script_path):
					os.remove(temp_script_path)
			except Exception:
				pass

			# Only clean up the sandbox dir in SAFE mode (we created it).
			if (not unsafe) and (sandbox_context is None) and safe_dir and os.path.exists(safe_dir):
				shutil.rmtree(safe_dir, ignore_errors=True)

	def _check_compilers(self, language):
		try:
			language = language.lower().strip()
			if language == "python":
				candidates = [["python3", "--version"], ["python", "--version"]]
			elif language == "javascript":
				candidates = [["node", "--version"]]
			else:
				self.logger.error("Invalid language selected.")
				return False

			for cmd in candidates:
				try:
					compiler = subprocess.run(cmd, capture_output=True, text=True)
					if compiler.returncode == 0:
						return True
				except FileNotFoundError:
					continue

			self.logger.error(f"{language.capitalize()} compiler not found.")
			return False
		except Exception as exception:
			self.logger.error(f"Error occurred while checking compilers: {exception}")
			raise Exception(f"Error occurred while checking compilers: {exception}")

	def save_code(self, filename='output/code_generated.py', code=None):
		"""
		Saves the provided code to a file.
		The default filename is 'code_generated.py'.
		"""
		try:
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

	def extract_code(self, code: str, start_sep='```', end_sep='```'):
		"""
		Extracts the code from the provided string.
		If the string contains the start and end separators, it extracts the code between them.
		Otherwise, it returns the original string.
		Leading markdown fence language lines (e.g. python, js, c++) are removed automatically.
		"""
		try:
			if code is None:
				self.logger.error("No content were generated by the LLM.")
				display_markdown_message("Error: **No content were generated by the LLM.**")
				return None

			if "```" in code and (start_sep == '`' or end_sep == '`'):
				start_sep = "```"
				end_sep = "```"

			if start_sep in code and end_sep in code:
				start = code.find(start_sep) + len(start_sep)
				if start < len(code) and code[start] == '\n':
					start += 1

				end = code.find(end_sep, start)
				if end > start and code[end - 1] == '\n':
					end -= 1

				extracted_code = code[start:end]
				extracted_code = _strip_leading_fence_language_line(extracted_code)

				self.logger.info("Code extracted successfully.")
				return extracted_code
			else:
				self.logger.info("No special characters found in the code. Returning the original code.")
				return code
		except Exception as exception:
			self.logger.error(f"Error occurred while extracting code: {exception}")
			raise Exception(f"Error occurred while extracting code: {exception}")

	def execute_code(self, code, language, sandbox_context=None):
		"""Execute code.
		In SAFE mode: sandbox, safety checks, timeout, resource limits apply.
		In UNSAFE mode: runs directly in the real working directory with the full
		environment, no timeout, no resource limits, no sandbox isolation.

		FIX: Python code is written to a temp .py file instead of using `python -c`
		to prevent watchdog/timeout crashes caused by multi-line code with subprocess
		calls (e.g., pip install + plotly chart rendering).
		"""
		language = language.lower()
		self.logger.info(f"Running code: {code[:100]} in language: {language}")

		unsafe = self._is_unsafe()

		# SAFETY CHECK — skipped in unsafe mode
		if not unsafe:
			decision = self.safety_manager.assess_execution(code, "code")
			if not decision.allowed:
				reason_text = "; ".join(decision.reasons)
				self.logger.warning(f"Safety blocked: {reason_text}")
				return None, f"Safety blocked: {reason_text}"

		if not code or len(code.strip()) == 0:
			return None, "Code is empty. Cannot execute an empty code."

		compilers_status = self._check_compilers(language)
		if not compilers_status:
			raise Exception("Compilers not found. Please install compilers on your system.")

		if unsafe:
			# UNSAFE MODE: real CWD, full env, no timeout, no resource limits.
			real_cwd = os.getcwd()
			popen_kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "cwd": real_cwd, "env": None}
			if os.name == "nt":
				creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
				creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
				popen_kwargs["creationflags"] = creationflags
			else:
				popen_kwargs["start_new_session"] = True
			timeout = None
			posix_extra = {}
		else:
			# SAFE MODE: sandboxed dir, filtered env, timeout, resource limits.
			base_kwargs = self._get_subprocess_security_kwargs(sandbox_context)
			popen_kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
			popen_kwargs.update(base_kwargs)
			timeout = getattr(sandbox_context, "timeout_seconds", MAX_TIMEOUT) if sandbox_context else MAX_TIMEOUT
			posix_extra = {"preexec_fn": _limit_resources} if os.name != "nt" else {}

			if sandbox_context and sandbox_context.cwd:
				safe_dir = sandbox_context.cwd
			else:
				safe_dir = tempfile.mkdtemp(prefix="ci_sandbox_")
			popen_kwargs["cwd"] = safe_dir

		process = None
		temp_code_path = None

		try:
			if language == "python":
				exec_bin = shutil.which("python3") or shutil.which("python") or "python"
				# Write code to a temp file instead of passing via -c.
				# Using -c causes watchdog/timeout crashes for complex multi-line code
				# that spawns subprocesses (e.g. pip install kaleido + plotly rendering).
				exec_dir = popen_kwargs.get("cwd") or tempfile.gettempdir()
				fd, temp_code_path = tempfile.mkstemp(prefix="ci_exec_", suffix=".py", dir=exec_dir)
				try:
					with os.fdopen(fd, "wb") as fh:
						fh.write(code.encode())
				except Exception:
					os.close(fd)
					raise
				args = [exec_bin, temp_code_path]
			elif language == "javascript":
				exec_bin = shutil.which("node") or "node"
				args = [exec_bin, "-e", code]
			else:
				self.logger.info("Unsupported language.")
				raise Exception("Unsupported language.")

			if os.name != "nt":
				process = subprocess.Popen(args, **popen_kwargs, **posix_extra)
			else:
				process = subprocess.Popen(args, **popen_kwargs)

			# Only apply timeout if one is set (no watchdog in unsafe mode)
			if timeout is not None:
				stdout, stderr = process.communicate(timeout=timeout)

			else:
				stdout, stderr = process.communicate()

			stdout_output = stdout.decode("utf-8", errors='replace') if stdout else ""
			stderr_output = stderr.decode("utf-8", errors='replace') if stderr else ""
			if len(stdout_output) > MAX_OUTPUT:
				stdout_output = stdout_output[:MAX_OUTPUT]
			if len(stderr_output) > MAX_OUTPUT:
				stderr_output = stderr_output[:MAX_OUTPUT]
			if language == "python":
				self.logger.debug(f"Python Output execution: {stdout_output}, Errors: {stderr_output}")
			else:
				self.logger.debug(f"JavaScript Output execution: {stdout_output}, Errors: {stderr_output}")
			return stdout_output, stderr_output
		except subprocess.TimeoutExpired:
			if process:
				_kill_process_group(process)
				try:
					process.communicate()
				except Exception:
					pass
			return None, "Execution timed out."
		finally:
			# Clean up temp code file if created.
			if temp_code_path:
				try:
					if os.path.exists(temp_code_path):
						os.remove(temp_code_path)
				except Exception:
					pass
			# Only clean up sandbox dir in SAFE mode when we created it.
			if (not unsafe) and (sandbox_context is None) and 'safe_dir' in locals() and safe_dir:
				try:
					shutil.rmtree(safe_dir, ignore_errors=True)
				except Exception:
					pass

	def execute_script(self, script: str, os_type: str = 'macos', sandbox_context=None):
		output = error = None
		try:
			if not script:
				raise ValueError("Script must be provided.")
			if not os_type:
				raise ValueError("OS type must be provided.")

			unsafe = self._is_unsafe()

			# SAFETY CHECK — skipped in unsafe mode
			if not unsafe:
				decision = self.safety_manager.assess_execution(script, "script")
				if not decision.allowed:
					reason_text = "; ".join(decision.reasons)
					self.logger.error(f"Execution blocked by safety policy: {reason_text}")
					return None, f"Safety blocked: {reason_text}"

			self.logger.info(f"Attempting to execute script: {script[:50]}")

			if not unsafe:
				if re.search(r'(C:\\|/etc/|/usr/|/var/)', script):
					return None, "Access to system paths is restricted."

			# Use ast.parse() to reliably detect Python code.
			is_python = _is_python_code(script)

			if 'darwin' in os_type.lower() or 'macos' in os_type.lower():
				shell = 'python' if is_python else 'bash'
				output, error = self._execute_script(script, shell=shell, sandbox_context=sandbox_context)
			elif 'linux' in os_type.lower():
				shell = 'python' if is_python else 'bash'
				output, error = self._execute_script(script, shell=shell, sandbox_context=sandbox_context)
			elif 'windows' in os_type.lower():
				output, error = self._execute_script(script, shell='python', sandbox_context=sandbox_context)
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

	def execute_command(self, command: str, sandbox_context=None):
		try:
			if not command:
				raise ValueError("Command must be provided.")

			unsafe = self._is_unsafe()

			# SAFETY CHECK — skipped in unsafe mode
			if not unsafe:
				decision = self.safety_manager.assess_execution(command, "command")
				if not decision.allowed:
					return None, f"Safety blocked: {'; '.join(decision.reasons)}"

			# Normalize command (convert shell-like commands → python -c)
			command = self._normalize_command(command)

			# Hard block destructive ops in SAFE mode only
			if not unsafe:
				if any(k in command for k in ["unlink(", "os.remove(", "rmtree", "del ", "rm "]):
					return None, "Blocked: destructive operation (LLM safety)."

			# Build safe invocation (no shell)
			args = self._build_command_invocation(command)

			# Subprocess config
			popen_kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE}

			if unsafe:
				# UNSAFE MODE: real CWD, full env, no timeout, no resource limits.
				popen_kwargs["cwd"] = os.getcwd()
				popen_kwargs["env"] = None
				if os.name == "nt":
					creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
					creationflags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
					popen_kwargs["creationflags"] = creationflags
				else:
					popen_kwargs["start_new_session"] = True
				timeout = None
				posix_extra = {}
			else:
				# SAFE MODE: sandboxed dir, filtered env, timeout, resource limits.
				base_kwargs = self._get_subprocess_security_kwargs(sandbox_context)
				popen_kwargs.update(base_kwargs)
				posix_extra = {"preexec_fn": _limit_resources} if os.name != "nt" else {}
				timeout = getattr(sandbox_context, "timeout_seconds", MAX_TIMEOUT) if sandbox_context else MAX_TIMEOUT

			process = None

			try:
				if os.name != "nt":
					process = subprocess.Popen(args, **popen_kwargs, **posix_extra)
				else:
					process = subprocess.Popen(args, **popen_kwargs)

				# Only apply timeout if one is set (no watchdog in unsafe mode)
				if timeout is not None:
					stdout, stderr = process.communicate(timeout=timeout)
					
				else:
					stdout, stderr = process.communicate()

				stdout_decoded = stdout.decode("utf-8", errors="ignore") if stdout else ""
				stderr_decoded = stderr.decode("utf-8", errors="ignore") if stderr else ""

				if len(stdout_decoded) > MAX_OUTPUT:
					stdout_decoded = stdout_decoded[:MAX_OUTPUT]
				if len(stderr_decoded) > MAX_OUTPUT:
					stderr_decoded = stderr_decoded[:MAX_OUTPUT]

				return stdout_decoded, stderr_decoded

			except subprocess.TimeoutExpired:
				if process:
					_kill_process_group(process)
					try:
						process.communicate()
					except Exception:
						pass
				return None, "Execution timed out."

		except Exception as e:
			return None, str(e)
