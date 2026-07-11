"""Execution helpers: sandbox wrapping and last-code replay."""

from __future__ import annotations


class CodeExecutor:
	"""Wraps Interpreter.execute_code with sandbox context management."""

	def __init__(self, interp):
		self.interp = interp

	def execute_generated_output(self, code_snippet, code_lang, force_execute=False):
		interp = self.interp
		if not interp.UNSAFE_EXECUTION:
			sandbox_context = interp.safety_manager.build_sandbox_context()
		else:
			sandbox_context = None

		output, error = interp.execute_code(
			code_snippet, code_lang, sandbox_context=sandbox_context, force_execute=force_execute
		)
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
