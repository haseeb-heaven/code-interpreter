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

# Extra minimal dangerous patterns guard (additional to ExecutionSafetyManager)
_SYSTEM_DANGEROUS_PATTERNS = [
	"rm -rf",
	"mkfs",
	":(){",
	"shutdown",
	"reboot",
]


def _limit_resources():
	"""Apply basic resource limits in the child process (Unix only).

	This function is safe to call on any platform — it will no-op when
	the `resource` module is unavailable (Windows).
	"""
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
			# Some platforms may not support RLIMIT_NPROC
			pass
	except Exception:
		# Be resilient: don't let resource limit failures crash the child setup
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

class CodeInterpreter:

	def __init__(self):
		self.logger = Logger.initialize("logs/code-interpreter.log")

	def _get_subprocess_security_kwargs(self, sandbox_context=None):
		# If no sandbox_context was provided, preserve that by returning
		# explicit None for `cwd` and `env`. Tests rely on this behavior.
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

		# When a sandbox_context object is provided, respect explicit values
		# (including explicit None). If the context provides an `env` dict,
		# whitelist only a minimal set of environment variables to avoid
		# leaking sensitive host env values into subprocesses.
		cwd = getattr(sandbox_context, "cwd", None)
		# Only build a safe env if the sandbox explicitly provides an `env`
		# attribute. If `env` is absent on the context, return None so callers
		# can detect that no env override was requested.
		allowed_keys = {"PATH", "HOME", "LANG"}
		if hasattr(sandbox_context, "env"):
			provided_env = getattr(sandbox_context, "env")
			if os.name == "nt":
				default_env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("USERPROFILE", ""), "LANG": os.environ.get("LANG", "C")}
			else:
				default_env = {"PATH": "/usr/bin:/bin", "HOME": tempfile.gettempdir(), "LANG": "C"}
			# Start from a safe baseline and selectively copy allowed keys from the
			# provided environment (if any).
			safe_env = default_env.copy()
			if isinstance(provided_env, dict):
				for k in allowed_keys:
					if k in provided_env and provided_env[k] is not None:
						safe_env[k] = provided_env[k]
				env = safe_env
			else:
				# Propagate explicit None or non-dict values as-is (so callers can
				# explicitly request no environment override by setting env=None).
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
		if any(keyword in command_lower for keyword in ["dir", "get-childitem", "ls"]):
			if ".txt" in command_lower:
				import re

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
		# Use simple shlex splitting for both POSIX and Windows. Do not
		# introduce a cmd.exe fallback here — callers (CLI) that need shell
		# semantics should invoke the appropriate high-level handler.
		command = command.strip()
		command_lower = command.lower()

		# FIX: preserve inline interpreters (avoid shlex breaking quotes/newlines)
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

			if command_lower.startswith("bash -c"):
				parts = command.split(" ", 2)
				if len(parts) < 3:
					raise ValueError("Invalid bash -c format")
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
				# Disallow obvious shell operators on Windows to enforce safe execution.
				if any(op in command for op in ["&", "|", "&&", ">", "<"]):
					raise ValueError("Shell operators not allowed")
				return parts
			except Exception as e:
				raise ValueError(f"Invalid command format: {command}") from e
	
	def _execute_script(self, script: str, shell: str, sandbox_context=None):
		"""Execute a script in an isolated temp directory with basic resource limits.

		This function avoids invoking a shell with "-lc". For multi-line script
		bodies we write a temporary script file and execute the interpreter on it.
		"""
		stdout_decoded = stderr_decoded = None
		process = None
		safe_dir = None
		temp_script_path = None
		try:
			popen_kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE}
			base_kwargs = self._get_subprocess_security_kwargs(sandbox_context)
			popen_kwargs.update(base_kwargs)

			# Create an isolated temp dir per execution
			safe_dir = tempfile.mkdtemp(prefix="ci_sandbox_")
			popen_kwargs["cwd"] = safe_dir

			# posix-only preexec to limit resources
			posix_extra = {"preexec_fn": _limit_resources} if os.name != "nt" else {}

			timeout = getattr(sandbox_context, "timeout_seconds", 30) if sandbox_context else 30

			# Quick extra substring guard (another layer beyond regex-based safety)
			lower_script = (script or "").lower()
			for pat in _SYSTEM_DANGEROUS_PATTERNS:
				if pat in lower_script:
					return None, f"Blocked dangerous command: {pat}"

			# ✅ NEW: Detect Python scripts and run with Python instead of shell
			if shell == "python":
				fd, temp_script_path = tempfile.mkstemp(prefix="ci_py_", suffix=".py", dir=safe_dir)
				with os.fdopen(fd, "wb") as fh:
					fh.write(script.encode())
					fh.flush()

				args = ["python", temp_script_path]

				if os.name != "nt":
					process = subprocess.Popen(args, **popen_kwargs, **posix_extra)
				else:
					process = subprocess.Popen(args, **popen_kwargs)

				stdout_val, stderr_val = process.communicate(timeout=timeout)

			elif shell == "bash":
				if "\n" in script or script.strip().startswith("#!") or any(ch in script for ch in ['|', '>', '<', ';', '&', '$', '`']):
					fd, temp_script_path = tempfile.mkstemp(prefix="ci_script_", suffix=".sh", dir=safe_dir)
					with os.fdopen(fd, "wb") as fh:
						fh.write(script.encode())
						fh.flush()
						os.chmod(temp_script_path, 0o700)
					if os.path.exists("/bin/bash"):
						args = ["/bin/bash", temp_script_path]
					else:
						args = ["bash", temp_script_path]
				else:
					args = shlex.split(script)

				if os.name != "nt":
					process = subprocess.Popen(args, **popen_kwargs, **posix_extra)
				else:
					process = subprocess.Popen(args, **popen_kwargs)

				stdout_val, stderr_val = process.communicate(timeout=timeout)

			elif shell == "powershell":

				popen_kwargs["env"] = os.environ.copy()

				pwsh = shutil.which("pwsh") or "powershell"

				fd, temp_script_path = tempfile.mkstemp(
					prefix="ci_ps_", suffix=".ps1", dir=safe_dir
				)
				with os.fdopen(fd, "wb") as fh:
					fh.write(script.encode())
					fh.flush()

				args = [
					pwsh,
					"-NoLogo",
					"-NoProfile",
					"-NonInteractive",
					"-ExecutionPolicy", "Bypass",
					"-File", temp_script_path
				]

				if os.name != "nt":
					process = subprocess.Popen(args, **popen_kwargs, **posix_extra)
				else:
					process = subprocess.Popen(args, **popen_kwargs)

				stdout_val, stderr_val = process.communicate(timeout=timeout)

			elif shell == "applescript":
				args = ["osascript", "-"]
				if os.name != "nt":
					process = subprocess.Popen(args, stdin=subprocess.PIPE, **popen_kwargs, **posix_extra)
				else:
					process = subprocess.Popen(args, stdin=subprocess.PIPE, **popen_kwargs)
				stdout_val, stderr_val = process.communicate(input=script.encode(), timeout=timeout)

			else:
				stderr_decoded = f"Invalid shell selected: {shell}"
				return (None, stderr_decoded)
			# Decode outputs
			stdout_decoded = stdout_val.decode(errors="ignore") if stdout_val else ""
			stderr_decoded = stderr_val.decode(errors="ignore") if stderr_val else ""

			return stdout_decoded, stderr_decoded

		except subprocess.TimeoutExpired:
			if process:
				process.kill()
			return None, "Execution timed out."

		except Exception as e:
			return None, str(e)

		finally:
			# Cleanup temp script if created
			try:
				if temp_script_path and os.path.exists(temp_script_path):
					os.remove(temp_script_path)
			except Exception:
				pass

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

			# Many legacy configs still specify single backticks, but modern providers
			# usually return fenced triple-backtick blocks. Prefer triple fences when present.
			if "```" in code and (start_sep == '`' or end_sep == '`'):
				start_sep = "```"
				end_sep = "```"

			if start_sep in code and end_sep in code:
				start = code.find(start_sep) + len(start_sep)
				# Skip the newline character after the start separator
				if start < len(code) and code[start] == '\n':
					start += 1
					
				end = code.find(end_sep, start)
				# Skip the newline character before the end separator
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
		# Run code in an isolated temp directory with resource limits and
		# safe subprocess argv usage to avoid shell injection.
		language = language.lower()
		self.logger.info(f"Running code: {code[:100]} in language: {language}")

		# SAFETY CHECK
		safety_manager = ExecutionSafetyManager()
		decision = safety_manager.assess_execution(code, "code")
		if not decision.allowed:
			reason_text = "; ".join(decision.reasons)
			self.logger.warning(f"Safety blocked: {reason_text}")
			return None, f"Safety blocked: {reason_text}"

		# Check for code and language validity
		if not code or len(code.strip()) == 0:
			return None, "Code is empty. Cannot execute an empty code."

		# Check for compilers on the system
		compilers_status = self._check_compilers(language)
		if not compilers_status:
			raise Exception("Compilers not found. Please install compilers on your system.")

		base_kwargs = self._get_subprocess_security_kwargs(sandbox_context)
		timeout = getattr(sandbox_context, "timeout_seconds", 30) if sandbox_context else 30
		# isolated execution directory
		safe_dir = tempfile.mkdtemp(prefix="ci_sandbox_")
		base_kwargs["cwd"] = safe_dir
		posix_extra = {"preexec_fn": _limit_resources} if os.name != "nt" else {}

		process = None
		try:
			if language == "python":
				exec_bin = shutil.which("python3") or shutil.which("python") or "python"
				args = [exec_bin, "-c", code]
			elif language == "javascript":
				exec_bin = shutil.which("node") or "node"
				args = [exec_bin, "-e", code]
			else:
				self.logger.info("Unsupported language.")
				raise Exception("Unsupported language.")

			# Launch the process with resource limits when supported
			if os.name != "nt":
				process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **base_kwargs, **posix_extra)
			else:
				process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **base_kwargs)

			stdout, stderr = process.communicate(timeout=timeout)
			stdout_output = stdout.decode("utf-8", errors='replace') if stdout else ""
			stderr_output = stderr.decode("utf-8", errors='replace') if stderr else ""
			if len(stdout_output) > MAX_OUTPUT:
				stdout_output = stdout_output[:MAX_OUTPUT]
			if len(stderr_output) > MAX_OUTPUT:
				stderr_output = stderr_output[:MAX_OUTPUT]
			# Log by language
			if language == "python":
				self.logger.info(f"Python Output execution: {stdout_output}, Errors: {stderr_output}")
			else:
				self.logger.info(f"JavaScript Output execution: {stdout_output}, Errors: {stderr_output}")
			return stdout_output, stderr_output
		except subprocess.TimeoutExpired:
			if process:
				try:
					if os.name != "nt":
						os.killpg(os.getpgid(process.pid), signal.SIGKILL)
					else:
						process.kill()
				except Exception:
					pass
				try:
					process.communicate()
				except Exception:
					pass
			return None, "Execution timed out."
		finally:
			try:
				shutil.rmtree(safe_dir)
			except Exception:
				pass
		
	def execute_script(self, script: str, os_type: str = 'macos', sandbox_context=None):
		output = error = None
		try:
			if not script:
				raise ValueError("Script must be provided.")
			if not os_type:
				raise ValueError("OS type must be provided.")

			# Check for dangerous patterns
			safety_manager = ExecutionSafetyManager()
			decision = safety_manager.assess_execution(script, "script")
			if not decision.allowed:
				reason_text = "; ".join(decision.reasons)
				self.logger.error(f"Execution blocked by safety policy: {reason_text}")
				return None, f"Safety blocked: {reason_text}"

			self.logger.info(f"Attempting to execute script: {script[:50]}")
			# Use a POSIX shell on macOS rather than AppleScript for general scripts
			if 'darwin' in os_type.lower() or 'macos' in os_type.lower():
				output, error = self._execute_script(script, shell='bash', sandbox_context=sandbox_context)
			elif 'linux' in os_type.lower():
				output, error = self._execute_script(script, shell='bash', sandbox_context=sandbox_context)
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
		
	def execute_command(self, command:str, sandbox_context=None):
		try:
			if not command:
				raise ValueError("Command must be provided.")

			# SAFETY CHECK
			safety_manager = ExecutionSafetyManager()
			decision = safety_manager.assess_execution(command, "command")
			if not decision.allowed:
				return None, f"Safety blocked: {'; '.join(decision.reasons)}"

			# Extra quick guard against very obvious destructive substrings
			lower_cmd = (command or "").lower()
			for pat in _SYSTEM_DANGEROUS_PATTERNS:
				if pat in lower_cmd:
					return None, f"Blocked dangerous command: {pat}"

			self.logger.info(f"Attempting to execute command: {command}")
			base_kwargs = self._get_subprocess_security_kwargs(sandbox_context)
			timeout = getattr(sandbox_context, "timeout_seconds", 30) if sandbox_context else 30
			# isolated execution dir per command
			safe_dir = tempfile.mkdtemp(prefix="ci_sandbox_")
			base_kwargs["cwd"] = safe_dir
			posix_extra = {"preexec_fn": _limit_resources} if os.name != "nt" else {}

			command = self._normalize_command(command)
			args = self._build_command_invocation(command)
			process = None
			try:
				# Launch the subprocess; handle missing executable errors gracefully
				try:
					if os.name != "nt":
						process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **base_kwargs, **posix_extra)
					else:
						process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **base_kwargs)
				except FileNotFoundError as fnf:
					# Executable not found (common on Windows for Unix commands like 'ls')
					msg = f"Executable not found: {args[0] if isinstance(args, (list, tuple)) and args else args}"
					if self.logger:
						self.logger.error(f"{msg}: {fnf}")
					try:
						shutil.rmtree(safe_dir)
					except Exception:
						pass
					return None, msg
				stdout, stderr = process.communicate(timeout=timeout)
				stdout_output = stdout.decode("utf-8", errors='replace') if stdout else ""
				stderr_output = stderr.decode("utf-8", errors='replace') if stderr else ""
				if len(stdout_output) > MAX_OUTPUT:
					stdout_output = stdout_output[:MAX_OUTPUT]
				if len(stderr_output) > MAX_OUTPUT:
					stderr_output = stderr_output[:MAX_OUTPUT]

				if stdout_output:
					self.logger.info(f"Command executed successfully with output: {stdout_output}")
				if stderr_output:
					self.logger.info(f"Command executed with error: {stderr_output}")

				return stdout_output, stderr_output
			except subprocess.TimeoutExpired:
				if process:
					try:
						if os.name != "nt":
							os.killpg(os.getpgid(process.pid), signal.SIGKILL)
						else:
							process.kill()
					except Exception:
						pass
					try:
						process.communicate()
					except Exception:
						pass
					return None, "Execution timed out."
			finally:
				try:
					shutil.rmtree(safe_dir)
				except Exception:
					pass
		except subprocess.TimeoutExpired:
			return None, "Execution timed out."
		except Exception as exception:
			self.logger.error(f"Error in executing command: {str(exception)}")
			raise exception