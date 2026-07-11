"""Execution helpers: sandbox wrapping and last-code replay."""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile


MAX_OUTPUT = 10_000_000


class CodeExecutor:
	"""Wraps Interpreter.execute_code with sandbox context management."""

	def __init__(self, interp):
		self.interp = interp

	def execute_generated_output(self, code_snippet, code_lang, force_execute=False):
		interp = self.interp
		# Auto-save matplotlib / plotly helpers (#222) + plot themes (#223)
		try:
			from libs.execution.auto_install import auto_install_missing
			from libs.execution.output_truncation import format_output
			from libs.output.chart_manager import inject_auto_save
			from libs.output.plot_themes import inject_plot_theme
			from libs.output.plotly_manager import inject_plotly_helper

			auto_install_missing(
				code_snippet or "",
				enabled=not bool(getattr(interp.args, "no_auto_install", False)),
			)
			code_snippet = inject_auto_save(code_snippet or "")
			code_snippet = inject_plotly_helper(code_snippet)
			theme = getattr(interp.args, "plot_theme", None)
			code_snippet = inject_plot_theme(code_snippet, theme)
		except Exception as exc:
			interp.logger.debug("Chart/theme/install hook skipped: %s", exc)

		if not interp.UNSAFE_EXECUTION:
			sandbox_context = interp.safety_manager.build_sandbox_context()
		else:
			sandbox_context = None

		output, error = interp.execute_code(
			code_snippet, code_lang, sandbox_context=sandbox_context, force_execute=force_execute
		)
		# Record notebook cell + truncate display output (#223)
		try:
			from libs.data.repl_data_commands import ensure_data_session
			from libs.execution.output_truncation import format_output

			session = ensure_data_session(interp)
			session.record_cell("code", code_snippet or "", output or error or "")
			interp._last_full_output = output or error or ""
			if output and not getattr(interp, "_output_full", False):
				output = format_output(output)
		except Exception as exc:
			interp.logger.debug("Output post-process skipped: %s", exc)

		if error:
			return None, error, sandbox_context

		return output, None, sandbox_context

	def execute_last_code(self, os_name, *, display_code_fn, display_markdown_fn):
		interp = self.interp
		try:
			code_file, code_snippet = interp.utility_manager.get_output_history(
				mode=interp.INTERPRETER_MODE, os_name=os_name, language=interp.INTERPRETER_LANGUAGE
			)

			if code_snippet is None or code_file is None:
				interp.logger.error("Code history or file is empty.")
				display_markdown_fn(
					"Code history or file is empty. - Please use **-s** flag or **/save** command to save the code."
				)
				return

			display_code_fn(code_snippet)

			code_output, code_error, sandbox_context = interp._execute_generated_output(
				code_snippet, interp.INTERPRETER_LANGUAGE
			)
			if code_output:
				interp.logger.info(f"{interp.INTERPRETER_LANGUAGE} code executed successfully.")
				display_code_fn(code_output)
				interp.logger.info(f"Output: {code_output[:100]}")
			elif code_error:
				interp.logger.info(f"{interp.INTERPRETER_LANGUAGE} code executed with error.")
				display_markdown_fn(f"Error: {code_error}")
		except Exception as exception:
			interp.logger.error(f"Error in processing command run code: {str(exception)}")
			raise

	def execute_code(self, code, language, sandbox_context=None, force_execute=False):
		"""Prompt/safety-aware execution (Interpreter.execute_code body)."""
		interp = self.interp
		raw_language = language or ""
		interp.logger.info(
			f"Interpreter.execute_code: language={raw_language}, unsafe={interp.UNSAFE_EXECUTION}"
		)

		unsafe = bool(interp.UNSAFE_EXECUTION)

		if not code or not str(code).strip():
			return None, "Code is empty. Cannot execute an empty code."

		is_dangerous = interp.safety_manager.is_dangerous_operation(code)

		if not force_execute:
			if not unsafe and is_dangerous:
				decision = interp.safety_manager.assess_execution(code, "code")
				reason_text = "; ".join(decision.reasons) if decision.reasons else "Dangerous operation blocked."
				interp.logger.warning(f"Safety blocked (safe mode, no prompt): {reason_text}")
				return None, f"Safety blocked: {reason_text}"

			if is_dangerous:
				prompt_text = "Dangerous operation detected. Execute the code? Y/N "
			else:
				prompt_text = "Execute the code? Y/N "

			user_confirmation = interp._safe_input(prompt_text, default="n")
			if (user_confirmation or "n").strip().lower() not in ("y", "yes"):
				interp._last_execution_approved = False
				return None, None

			interp._last_execution_approved = True

		if not unsafe:
			decision = interp.safety_manager.assess_execution(code, "code")
			if not decision.allowed:
				reason_text = "; ".join(decision.reasons)
				interp.logger.warning(f"Safety blocked before execution: {reason_text}")
				return None, f"Safety blocked: {reason_text}"

		try:
			stdout, stderr = interp.code_interpreter.execute_code(
				code=code,
				language=language,
				sandbox_context=sandbox_context,
				force_execute=True,
			)
			return stdout, stderr
		except Exception as exc:
			interp.logger.error(f"Interpreter.execute_code failed: {exc}")
			return None, str(exc)

	async def execute_async(self, code, language, timeout=300):
		"""Execute generated code asynchronously without altering the sync execution path."""
		interp = self.interp
		language = (language or "").lower()
		if language in ("linux", "windows", "windows 10", "windows 11", "mac", "macos", "darwin"):
			language = "python"

		if not code or not str(code).strip():
			return None, "Code is empty. Cannot execute an empty code."

		unsafe = bool(getattr(interp, "UNSAFE_EXECUTION", False))
		if not unsafe and hasattr(interp, "safety_manager"):
			decision = interp.safety_manager.assess_execution(code, "code")
			if not decision.allowed:
				reason_text = "; ".join(decision.reasons)
				interp.logger.warning(f"Safety blocked before async execution: {reason_text}")
				return None, f"Safety blocked: {reason_text}"

		try:
			with tempfile.TemporaryDirectory(prefix="ci_async_") as exec_dir:
				if language == "python":
					exec_bin = shutil.which("python3") or shutil.which("python") or "python"
					fd, temp_code_path = tempfile.mkstemp(prefix="ci_exec_", suffix=".py", dir=exec_dir)
					try:
						with os.fdopen(fd, "wb") as fh:
							fh.write(str(code).encode())
					except Exception:
						os.close(fd)
						raise
					args = [exec_bin, temp_code_path]
				elif language == "javascript":
					exec_bin = shutil.which("node") or "node"
					args = [exec_bin, "-e", str(code)]
				else:
					interp.logger.info("Unsupported language.")
					return None, "Unsupported language."

				process = await asyncio.create_subprocess_exec(
					*args,
					stdout=asyncio.subprocess.PIPE,
					stderr=asyncio.subprocess.PIPE,
					cwd=os.getcwd() if unsafe else exec_dir,
					start_new_session=(os.name != "nt"),
				)
				try:
					stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
				except asyncio.TimeoutError:
					process.kill()
					await process.wait()
					return None, "Execution timed out."

				stdout_output = stdout.decode("utf-8", errors="replace") if stdout else ""
				stderr_output = stderr.decode("utf-8", errors="replace") if stderr else ""
				return stdout_output[:MAX_OUTPUT], stderr_output[:MAX_OUTPUT]
		except Exception as exc:
			interp.logger.error(f"Interpreter.execute_async failed: {exc}")
			return None, str(exc)
