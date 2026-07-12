"""Bounded repair loop after failed code execution."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import Callable

from libs.vision.image_handler import image_file_arg_for_path


@dataclass
class RepairCircuitBreaker:
	"""Stop repairing when the same error repeats or attempts are exhausted."""

	max_attempts: int = 3
	attempts: int = 0
	seen_errors: set[str] = field(default_factory=set)

	def should_continue(self, error_text: str) -> bool:
		normalized = self._normalize_error(error_text)

		if normalized in self.seen_errors:
			return False

		if self.attempts >= self.max_attempts:
			return False

		self.seen_errors.add(normalized)
		self.attempts += 1
		return True

	def _normalize_error(self, error_text: str) -> str:
		error_text = (error_text or "").strip().lower()
		error_text = re.sub(r"\s+", " ", error_text)
		return error_text


class Repairer:
	"""Owns repair-prompt construction and the bounded repair loop."""

	def __init__(self, interp):
		self.interp = interp

	def build_repair_prompt(self, task, prompt, code_snippet, error_text, os_name, code_output=None):
		interp = self.interp
		if interp.COMMAND_MODE:
			target = "single terminal command"
		elif interp.SCRIPT_MODE:
			target = "script"
		else:
			target = f"{interp.INTERPRETER_LANGUAGE} code"

		observed_output = ""
		if code_output:
			observed_output = f"\nObserved stdout before failure:\n{code_output}\n"

		return (
			f"You are in bounded repair mode for a failed {target} execution.\n"
			f"Original task: {task}\n"
			f"Resolved prompt: {prompt}\n"
			f"Operating system: {os_name}\n"
			f"Generated content:\n{code_snippet}\n\n"
			f"{observed_output}"
			f"Execution error:\n{error_text}\n\n"
			f"Think through the failure privately, then return only the corrected {target} inside one triple-backtick block.\n"
			"Preserve only the parts that help complete the original task, and remove unrelated extras.\n"
			"Do not include explanations, comments, or any text outside the code block."
		)

	def attempt_repair_after_failure(
		self,
		task,
		prompt,
		code_snippet,
		code_error,
		os_name,
		start_sep,
		end_sep,
		extracted_file_name,
		code_output=None,
		*,
		display_code_fn: Callable,
		display_markdown_fn: Callable,
	):
		interp = self.interp
		circuit_breaker = RepairCircuitBreaker(max_attempts=interp.MAX_REPAIR_ATTEMPTS)
		current_snippet = code_snippet
		current_error = code_error
		current_output = code_output

		while current_error and circuit_breaker.should_continue(current_error):
			display_markdown_fn(
				f"Repair attempt {circuit_breaker.attempts}/{circuit_breaker.max_attempts} after execution failure."
			)
			repair_prompt = interp._build_repair_prompt(
				task, prompt, current_snippet, current_error, os_name, code_output=current_output
			)
			repaired_output = interp._generate_content_with_retries(
				repair_prompt, interp.history, config_values=interp.config_values, image_file=image_file_arg_for_path(extracted_file_name)
			)
			repaired_snippet = interp.code_interpreter.extract_code(repaired_output, start_sep, end_sep)
			repaired_snippet = interp._maybe_simplify_generated_code(task, repaired_snippet)

			if not repaired_snippet:
				current_error = "Failed to extract repaired output from model response."
				continue

			if repaired_snippet.strip() == current_snippet.strip():
				current_output, current_error, sandbox_ctx = interp._execute_generated_output(
					repaired_snippet, interp.INTERPRETER_LANGUAGE, force_execute=False
				)
				if sandbox_ctx:
					interp.safety_manager.cleanup_sandbox_context(sandbox_ctx)
				if current_output:
					return repaired_snippet, current_output, current_error
				if not current_error:
					return repaired_snippet, current_output, None
				if current_error.startswith("Safety blocked:"):
					return repaired_snippet, current_output, current_error
				break

			current_snippet = repaired_snippet
			display_language = interp.INTERPRETER_LANGUAGE if interp.CODE_MODE else "bash"
			display_code_fn(current_snippet, language=display_language)
			current_output, current_error, sandbox_ctx = interp._execute_generated_output(
				current_snippet, interp.INTERPRETER_LANGUAGE, force_execute=False
			)
			if sandbox_ctx:
				interp.safety_manager.cleanup_sandbox_context(sandbox_ctx)

			if current_output:
				return current_snippet, current_output, current_error
			if not current_error:
				return current_snippet, current_output, None
			if current_error.startswith("Safety blocked:"):
				return current_snippet, current_output, current_error

		return current_snippet, current_output, current_error

	async def attempt_repair_async(
		self,
		task,
		prompt,
		code_snippet,
		code_error,
		os_name,
		start_sep,
		end_sep,
		extracted_file_name,
		code_output=None,
		*,
		display_code_fn: Callable,
		display_markdown_fn: Callable,
	):
		interp = self.interp
		circuit_breaker = RepairCircuitBreaker(max_attempts=interp.MAX_REPAIR_ATTEMPTS)
		current_snippet = code_snippet
		current_error = code_error
		current_output = code_output

		while current_error and circuit_breaker.should_continue(current_error):
			if circuit_breaker.attempts > 1:
				await asyncio.sleep(min(circuit_breaker.attempts - 1, 3))

			display_markdown_fn(
				f"Repair attempt {circuit_breaker.attempts}/{circuit_breaker.max_attempts} after execution failure."
			)
			repair_prompt = interp._build_repair_prompt(
				task, prompt, current_snippet, current_error, os_name, code_output=current_output
			)
			generate_repair = getattr(interp, "_generate_content_with_retries_async", None)
			if generate_repair:
				repaired_output = await generate_repair(
					repair_prompt, interp.history, config_values=interp.config_values, image_file=image_file_arg_for_path(extracted_file_name)
				)
			else:
				repaired_output = await asyncio.to_thread(
					interp._generate_content_with_retries,
					repair_prompt, interp.history,
					config_values=interp.config_values, image_file=image_file_arg_for_path(extracted_file_name),
				)
			repaired_snippet = interp.code_interpreter.extract_code(repaired_output, start_sep, end_sep)
			repaired_snippet = interp._maybe_simplify_generated_code(task, repaired_snippet)

			if not repaired_snippet:
				current_error = "Failed to extract repaired output from model response."
				continue

			if repaired_snippet.strip() == current_snippet.strip():
				execute_async = getattr(interp.executor, "execute_async", None)
				if execute_async:
					current_output, current_error = await execute_async(
						repaired_snippet, interp.INTERPRETER_LANGUAGE
					)
					sandbox_ctx = None
				else:
					current_output, current_error, sandbox_ctx = await asyncio.to_thread(
						interp._execute_generated_output,
						repaired_snippet, interp.INTERPRETER_LANGUAGE,
						force_execute=False,
					)
				if sandbox_ctx:
					interp.safety_manager.cleanup_sandbox_context(sandbox_ctx)
				if current_output:
					return repaired_snippet, current_output, current_error
				if not current_error:
					return repaired_snippet, current_output, None
				if current_error.startswith("Safety blocked:"):
					return repaired_snippet, current_output, current_error
				break

			current_snippet = repaired_snippet
			display_language = interp.INTERPRETER_LANGUAGE if interp.CODE_MODE else "bash"
			display_code_fn(current_snippet, language=display_language)
			execute_async = getattr(interp.executor, "execute_async", None)
			if execute_async:
				current_output, current_error = await execute_async(
					current_snippet, interp.INTERPRETER_LANGUAGE
				)
				sandbox_ctx = None
			else:
				current_output, current_error, sandbox_ctx = await asyncio.to_thread(
					interp._execute_generated_output,
					current_snippet, interp.INTERPRETER_LANGUAGE,
					force_execute=False,
				)
			if sandbox_ctx:
				interp.safety_manager.cleanup_sandbox_context(sandbox_ctx)

			if current_output:
				return current_snippet, current_output, current_error
			if not current_error:
				return current_snippet, current_output, None
			if current_error.startswith("Safety blocked:"):
				return current_snippet, current_output, current_error

		return current_snippet, current_output, current_error
